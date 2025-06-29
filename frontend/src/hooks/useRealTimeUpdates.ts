import { useEffect, useRef } from 'react';
import { API, graphqlOperation } from 'aws-amplify';
import { GraphQLSubscription } from '@aws-amplify/api';
import { useQueryClient } from 'react-query';
import { useNotificationContext } from '@/contexts/NotificationContext';
import {
  ON_INCIDENT_UPDATE,
  ON_TIMELINE_UPDATE,
  ON_NEW_INCIDENT,
  ON_STATUS_CHANGE,
} from '@/graphql/queries';
import { Incident, TimelineEvent } from '@/types';

export const useRealTimeUpdates = () => {
  const queryClient = useQueryClient();
  const { addNotification } = useNotificationContext();
  const subscriptionsRef = useRef<any[]>([]);

  useEffect(() => {
    // Subscribe to new incidents
    const newIncidentSub = API.graphql<GraphQLSubscription<any>>(
      graphqlOperation(ON_NEW_INCIDENT)
    ).subscribe({
      next: ({ value }) => {
        const newIncident = value.data?.onNewIncident;
        if (newIncident) {
          // Invalidate incident list queries
          queryClient.invalidateQueries(['incidents']);
          queryClient.invalidateQueries(['dashboardMetrics']);

          // Add notification
          addNotification({
            type: 'info',
            title: 'New Incident',
            message: `${newIncident.title} (${newIncident.severity})`,
            metadata: {
              incidentId: newIncident.id,
              severity: newIncident.severity,
            },
          });
        }
      },
      error: (error) => console.error('New incident subscription error:', error),
    });

    // Subscribe to status changes
    const statusChangeSub = API.graphql<GraphQLSubscription<any>>(
      graphqlOperation(ON_STATUS_CHANGE)
    ).subscribe({
      next: ({ value }) => {
        const statusChange = value.data?.onStatusChange;
        if (statusChange) {
          // Update cached incident data
          queryClient.setQueryData<Incident>(
            ['incident', statusChange.incidentId],
            (oldData) => {
              if (oldData) {
                return {
                  ...oldData,
                  status: statusChange.newStatus,
                  updatedAt: statusChange.changedAt,
                };
              }
              return oldData;
            }
          );

          // Invalidate related queries
          queryClient.invalidateQueries(['incidents']);
          queryClient.invalidateQueries(['dashboardMetrics']);

          // Add notification for critical status changes
          if (
            statusChange.newStatus === 'ACKNOWLEDGED' ||
            statusChange.newStatus === 'RESOLVED'
          ) {
            addNotification({
              type: 'success',
              title: 'Status Updated',
              message: `Incident ${statusChange.incidentId} is now ${statusChange.newStatus}`,
              metadata: {
                incidentId: statusChange.incidentId,
              },
            });
          }
        }
      },
      error: (error) => console.error('Status change subscription error:', error),
    });

    // Store subscriptions for cleanup
    subscriptionsRef.current = [newIncidentSub, statusChangeSub];

    // Cleanup function
    return () => {
      subscriptionsRef.current.forEach((sub) => {
        if (sub && typeof sub.unsubscribe === 'function') {
          sub.unsubscribe();
        }
      });
    };
  }, [queryClient, addNotification]);

  // Hook to subscribe to specific incident updates
  const subscribeToIncident = (incidentId: string) => {
    const incidentUpdateSub = API.graphql<GraphQLSubscription<any>>(
      graphqlOperation(ON_INCIDENT_UPDATE, { id: incidentId })
    ).subscribe({
      next: ({ value }) => {
        const updatedIncident = value.data?.onIncidentUpdate;
        if (updatedIncident) {
          // Update cache
          queryClient.setQueryData<Incident>(
            ['incident', incidentId],
            updatedIncident
          );
        }
      },
      error: (error) =>
        console.error('Incident update subscription error:', error),
    });

    const timelineUpdateSub = API.graphql<GraphQLSubscription<any>>(
      graphqlOperation(ON_TIMELINE_UPDATE, { incidentId })
    ).subscribe({
      next: ({ value }) => {
        const newEvent = value.data?.onTimelineUpdate;
        if (newEvent) {
          // Update timeline in cache
          queryClient.setQueryData<Incident>(
            ['incident', incidentId],
            (oldData) => {
              if (oldData && oldData.timeline) {
                return {
                  ...oldData,
                  timeline: [...oldData.timeline, newEvent],
                };
              }
              return oldData;
            }
          );
        }
      },
      error: (error) =>
        console.error('Timeline update subscription error:', error),
    });

    return () => {
      incidentUpdateSub.unsubscribe();
      timelineUpdateSub.unsubscribe();
    };
  };

  return {
    subscribeToIncident,
  };
};