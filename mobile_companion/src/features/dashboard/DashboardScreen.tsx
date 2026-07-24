import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert } from 'react-native';
import { connectionManager } from '../../core/network/ConnectionManager';
import { wsClient } from '../../core/api/WebSocketClient';
import { apiClient } from '../../core/api/ApiClient';
import { router } from 'expo-router';

export default function DashboardScreen() {
  const [latency, setLatency] = useState<number | null>(null);
  const [serverUrl, setServerUrl] = useState<string>('');
  const [systemStatus, setSystemStatus] = useState<any>(null);

  useEffect(() => {
    const conn = connectionManager.getCurrentConnection();
    if (conn) {
      setLatency(conn.latencyMs || null);
      setServerUrl(conn.url);
    }

    // Periodically fetch system status
    fetchSystemStatus();
    const interval = setInterval(fetchSystemStatus, 10000);

    return () => clearInterval(interval);
  }, []);

  const fetchSystemStatus = async () => {
    try {
      const response = await apiClient.getSystemStatus();
      setSystemStatus(response.data);
    } catch (e) {
      console.warn('Failed to fetch system status', e);
    }
  };

  const handleQuickAction = async (action: 'shutdown' | 'restart' | 'lock') => {
    Alert.alert(
      'Confirm Action',
      `Are you sure you want to ${action} the PC?`,
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Confirm', 
          style: 'destructive',
          onPress: async () => {
            try {
              await apiClient.powerControl(action);
              Alert.alert('Success', `Command '${action}' sent.`);
            } catch (e) {
              Alert.alert('Error', `Failed to execute ${action}`);
            }
          }
        }
      ]
    );
  };

  const handleDisconnect = () => {
    wsClient.disconnect();
    connectionManager.disconnect();
    router.replace('/');
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Genie</Text>
          <Text style={styles.headerSubtitle}>Connected: {serverUrl}</Text>
          {latency && <Text style={styles.headerSubtitle}>Latency: {latency}ms</Text>}
        </View>
        <TouchableOpacity style={styles.disconnectButton} onPress={handleDisconnect}>
          <Text style={styles.disconnectText}>Disconnect</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.vitalsContainer}>
        <Text style={styles.sectionTitle}>System Vitals</Text>
        <View style={styles.vitalsGrid}>
          <View style={styles.vitalCard}>
            <Text style={styles.vitalLabel}>CPU</Text>
            <Text style={styles.vitalValue}>{systemStatus ? 'Active' : '--'}</Text>
          </View>
          <View style={styles.vitalCard}>
            <Text style={styles.vitalLabel}>Tasks</Text>
            <Text style={styles.vitalValue}>{systemStatus?.kernel?.recent_task_count || '--'}</Text>
          </View>
          <View style={styles.vitalCard}>
            <Text style={styles.vitalLabel}>Events</Text>
            <Text style={styles.vitalValue}>{systemStatus?.kernel?.recent_event_count || '--'}</Text>
          </View>
        </View>
      </View>

      <View style={styles.actionsContainer}>
        <TouchableOpacity style={styles.chatButton} onPress={() => router.push('/chat')}>
          <Text style={styles.chatButtonText}>Open Genie Chat</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.actionsContainer}>
        <Text style={styles.sectionTitle}>Quick Actions</Text>
        <View style={styles.actionsGrid}>
          <TouchableOpacity style={styles.actionButton} onPress={() => handleQuickAction('lock')}>
            <Text style={styles.actionText}>Lock PC</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionButton} onPress={() => handleQuickAction('sleep')}>
            <Text style={styles.actionText}>Sleep</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.actionButton, styles.dangerButton]} onPress={() => handleQuickAction('restart')}>
            <Text style={styles.actionText}>Restart</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.actionButton, styles.dangerButton]} onPress={() => handleQuickAction('shutdown')}>
            <Text style={styles.actionText}>Shutdown</Text>
          </TouchableOpacity>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 24,
    paddingTop: 60,
    backgroundColor: '#1E293B',
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  headerSubtitle: {
    fontSize: 14,
    color: '#94A3B8',
    marginTop: 4,
  },
  disconnectButton: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#EF4444',
  },
  disconnectText: {
    color: '#EF4444',
    fontWeight: '600',
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginBottom: 16,
  },
  vitalsContainer: {
    padding: 24,
  },
  vitalsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  vitalCard: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 16,
    flex: 1,
    marginHorizontal: 4,
    alignItems: 'center',
  },
  vitalLabel: {
    color: '#94A3B8',
    fontSize: 14,
    marginBottom: 8,
  },
  vitalValue: {
    color: '#F8FAFC',
    fontSize: 24,
    fontWeight: 'bold',
  },
  actionsContainer: {
    padding: 24,
    paddingTop: 0,
  },
  chatButton: {
    backgroundColor: '#3B82F6',
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 16,
  },
  chatButtonText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  actionButton: {
    backgroundColor: '#1E293B',
    width: '48%',
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 16,
  },
  dangerButton: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderColor: '#EF4444',
    borderWidth: 1,
  },
  actionText: {
    color: '#F8FAFC',
    fontWeight: '600',
    fontSize: 16,
  },
});
