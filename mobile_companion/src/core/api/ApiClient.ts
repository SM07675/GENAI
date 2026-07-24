import axios from 'axios';
import { secureStorage } from '../storage/SecureStorage';

class ApiClient {
  private async getBaseUrl() {
    return await secureStorage.getServerUrl();
  }

  private async getHeaders() {
    const token = await secureStorage.getToken();
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }

  async get(endpoint: string, params?: Record<string, any>) {
    const baseUrl = await this.getBaseUrl();
    if (!baseUrl) throw new Error('No server URL configured');

    const headers = await this.getHeaders();
    return axios.get(`${baseUrl}${endpoint}`, { headers, params });
  }

  async post(endpoint: string, data?: any) {
    const baseUrl = await this.getBaseUrl();
    if (!baseUrl) throw new Error('No server URL configured');

    const headers = await this.getHeaders();
    return axios.post(`${baseUrl}${endpoint}`, data, { headers });
  }
  
  // Specific Genie API calls
  async getSystemStatus() {
    return this.get('/api/v1/system/status');
  }
  
  async invokeTool(toolName: string, argumentsObj: any = {}) {
    return this.post(`/api/v1/tools/${toolName}/invoke`, { arguments: argumentsObj });
  }

  async powerControl(action: 'shutdown' | 'restart' | 'lock') {
    return this.post(`/api/v1/mobile/${action}`);
  }

  async readClipboard() {
    return this.get('/api/v1/mobile/clipboard');
  }

  async takeScreenshot() {
    return this.post('/api/v1/mobile/screen');
  }
}

export const apiClient = new ApiClient();
