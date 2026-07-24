import React, { useEffect, useState } from 'react';
import { router } from 'expo-router';
import AuthScreen from '../features/auth/AuthScreen';
import { secureStorage } from '../core/storage/SecureStorage';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { wsClient } from '../core/api/WebSocketClient';
import { connectionManager } from '../core/network/ConnectionManager';

export default function Index() {
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    checkAutoLogin();
  }, []);

  const checkAutoLogin = async () => {
    const url = await secureStorage.getServerUrl();
    const pin = await secureStorage.getPin();
    
    if (url && pin) {
      console.log('Attempting auto-login...');
      const isConnected = await connectionManager.validateAndConnect(url, 'custom');
      if (isConnected) {
        wsClient.connect(url, pin);
        
        // Timeout for auto login
        const timeout = setTimeout(() => {
          setIsChecking(false);
        }, 5000);

        const unsubscribe = wsClient.subscribeToStatus((status) => {
          if (status === 'connected') {
            clearTimeout(timeout);
            unsubscribe();
            router.replace('/dashboard');
          } else if (status === 'auth_failed' || status === 'error') {
            clearTimeout(timeout);
            unsubscribe();
            setIsChecking(false);
          }
        });
        return;
      }
    }
    setIsChecking(false);
  };

  if (isChecking) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#3B82F6" />
      </View>
    );
  }

  return <AuthScreen onLoginSuccess={() => router.replace('/dashboard')} />;
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    backgroundColor: '#0F172A',
    justifyContent: 'center',
    alignItems: 'center',
  }
});
