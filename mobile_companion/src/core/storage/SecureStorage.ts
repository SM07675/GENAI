import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const isWeb = Platform.OS === 'web';

class SecureStorage {
  async setItem(key: string, value: string): Promise<boolean> {
    try {
      if (isWeb) {
        localStorage.setItem(key, value);
      } else {
        await SecureStore.setItemAsync(key, value);
      }
      return true;
    } catch (error) {
      console.error(`[SecureStorage] Failed to save ${key}:`, error);
      return false;
    }
  }

  async getItem(key: string): Promise<string | null> {
    try {
      if (isWeb) {
        return localStorage.getItem(key);
      }
      return await SecureStore.getItemAsync(key);
    } catch (error) {
      console.error(`[SecureStorage] Failed to get ${key}:`, error);
      return null;
    }
  }

  async removeItem(key: string): Promise<boolean> {
    try {
      if (isWeb) {
        localStorage.removeItem(key);
      } else {
        await SecureStore.deleteItemAsync(key);
      }
      return true;
    } catch (error) {
      console.error(`[SecureStorage] Failed to remove ${key}:`, error);
      return false;
    }
  }

  // Domain specific helpers
  async saveServerUrl(url: string) {
    return this.setItem('SERVER_URL', url);
  }

  async getServerUrl() {
    return this.getItem('SERVER_URL');
  }

  async saveToken(token: string) {
    return this.setItem('AUTH_TOKEN', token);
  }

  async getToken() {
    return this.getItem('AUTH_TOKEN');
  }

  async savePin(pin: string) {
    return this.setItem('AUTH_PIN', pin);
  }

  async getPin() {
    return this.getItem('AUTH_PIN');
  }

  async clearAll() {
    await this.removeItem('SERVER_URL');
    await this.removeItem('AUTH_TOKEN');
    await this.removeItem('AUTH_PIN');
  }
}

export const secureStorage = new SecureStorage();
