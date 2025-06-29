import { apiService, buildQueryString } from './api';
import {
  Incident,
  CreateIncidentInput,
  UpdateIncidentInput,
  IncidentConnection,
  ListIncidentsParams,
  TimelineEvent,
  Comment,
} from '@/types';

class IncidentService {
  private readonly basePath = '/incidents';

  // Create a new incident
  async createIncident(input: CreateIncidentInput): Promise<Incident> {
    return apiService.post<Incident>(this.basePath, input);
  }

  // Get a single incident by ID
  async getIncident(incidentId: string): Promise<Incident> {
    return apiService.get<Incident>(`${this.basePath}/${incidentId}`);
  }

  // List incidents with optional filters
  async listIncidents(params?: ListIncidentsParams): Promise<IncidentConnection> {
    const queryString = params ? buildQueryString(params) : '';
    return apiService.get<IncidentConnection>(`${this.basePath}${queryString}`);
  }

  // Update incident details
  async updateIncident(input: UpdateIncidentInput): Promise<Incident> {
    const { id, ...updateData } = input;
    return apiService.put<Incident>(`${this.basePath}/${id}`, updateData);
  }

  // Update incident status
  async updateStatus(
    incidentId: string,
    status: string,
    reason?: string
  ): Promise<Incident> {
    return apiService.patch<Incident>(`${this.basePath}/${incidentId}/status`, {
      status,
      reason,
    });
  }

  // Acknowledge incident
  async acknowledgeIncident(incidentId: string): Promise<Incident> {
    return apiService.post<Incident>(
      `${this.basePath}/${incidentId}/acknowledge`
    );
  }

  // Resolve incident
  async resolveIncident(
    incidentId: string,
    resolution: string
  ): Promise<Incident> {
    return apiService.post<Incident>(`${this.basePath}/${incidentId}/resolve`, {
      resolution,
    });
  }

  // Close incident
  async closeIncident(incidentId: string): Promise<Incident> {
    return apiService.post<Incident>(`${this.basePath}/${incidentId}/close`);
  }

  // Get incident timeline
  async getTimeline(incidentId: string): Promise<TimelineEvent[]> {
    return apiService.get<TimelineEvent[]>(
      `${this.basePath}/${incidentId}/timeline`
    );
  }

  // Add comment to incident
  async addComment(incidentId: string, text: string): Promise<Comment> {
    return apiService.post<Comment>(`${this.basePath}/${incidentId}/comments`, {
      text,
    });
  }

  // Get incident comments
  async getComments(incidentId: string): Promise<Comment[]> {
    return apiService.get<Comment[]>(
      `${this.basePath}/${incidentId}/comments`
    );
  }

  // Join incident as participant
  async joinIncident(incidentId: string, role: string): Promise<void> {
    return apiService.post(`${this.basePath}/${incidentId}/join`, { role });
  }

  // Leave incident
  async leaveIncident(incidentId: string): Promise<void> {
    return apiService.post(`${this.basePath}/${incidentId}/leave`);
  }

  // Export incident report
  async exportReport(
    incidentId: string,
    format: 'pdf' | 'markdown' = 'pdf'
  ): Promise<Blob> {
    const response = await apiService.get<Blob>(
      `${this.basePath}/${incidentId}/export`,
      {
        params: { format },
        responseType: 'blob',
      }
    );
    return response;
  }

  // Get incident statistics
  async getStatistics(incidentId: string): Promise<any> {
    return apiService.get(`${this.basePath}/${incidentId}/statistics`);
  }

  // Trigger AI summary generation
  async generateSummary(incidentId: string): Promise<void> {
    return apiService.post(`${this.basePath}/${incidentId}/generate-summary`);
  }

  // Get related incidents
  async getRelatedIncidents(incidentId: string): Promise<Incident[]> {
    return apiService.get<Incident[]>(
      `${this.basePath}/${incidentId}/related`
    );
  }

  // Escalate incident
  async escalateIncident(
    incidentId: string,
    escalationLevel: string,
    reason: string
  ): Promise<void> {
    return apiService.post(`${this.basePath}/${incidentId}/escalate`, {
      escalationLevel,
      reason,
    });
  }

  // Bulk update incidents
  async bulkUpdate(
    incidentIds: string[],
    updates: Partial<UpdateIncidentInput>
  ): Promise<void> {
    return apiService.post(`${this.basePath}/bulk-update`, {
      incidentIds,
      updates,
    });
  }

  // Search incidents
  async searchIncidents(query: string): Promise<Incident[]> {
    return apiService.get<Incident[]>(`${this.basePath}/search`, {
      params: { q: query },
    });
  }

  // Get incident metrics
  async getIncidentMetrics(timeRange: {
    start: string;
    end: string;
  }): Promise<any> {
    return apiService.get(`${this.basePath}/metrics`, {
      params: timeRange,
    });
  }
}

// Create singleton instance
export const incidentService = new IncidentService();