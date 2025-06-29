import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';
import { Auth } from 'aws-amplify';
import awsConfig from '@/aws-exports';

// Types
interface ApiError {
  message: string;
  code?: string;
  details?: any;
}

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: awsConfig.aws_api_gateway_endpoint,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      async (config) => {
        try {
          const session = await Auth.currentSession();
          const token = session.getIdToken().getJwtToken();
          config.headers.Authorization = `Bearer ${token}`;
        } catch (error) {
          console.error('Failed to get auth token:', error);
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError<ApiError>) => {
        if (error.response?.status === 401) {
          // Token expired, try to refresh
          try {
            await Auth.currentSession();
            // Retry the original request
            return this.client.request(error.config as AxiosRequestConfig);
          } catch (refreshError) {
            // Refresh failed, redirect to login
            window.location.href = '/login';
          }
        }

        const errorMessage =
          error.response?.data?.message ||
          error.message ||
          'An unexpected error occurred';

        return Promise.reject({
          message: errorMessage,
          code: error.response?.data?.code,
          status: error.response?.status,
          details: error.response?.data?.details,
        });
      }
    );
  }

  // Generic request methods
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<T>(url, config);
    return response.data;
  }

  async post<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  async put<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.client.put<T>(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }

  async patch<T>(
    url: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.client.patch<T>(url, data, config);
    return response.data;
  }
}

// Create singleton instance
export const apiService = new ApiService();

// Helper function to build query strings
export function buildQueryString(params: Record<string, any>): string {
  const queryParams = new URLSearchParams();
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      queryParams.append(key, String(value));
    }
  });
  
  const queryString = queryParams.toString();
  return queryString ? `?${queryString}` : '';
}