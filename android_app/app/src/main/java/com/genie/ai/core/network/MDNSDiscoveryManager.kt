package com.genie.ai.core.network

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.net.InetAddress

data class DiscoveredPC(
    val serviceName: String,
    val hostAddress: String,
    val port: Int
)

/**
 * mDNS Zeroconf Service Discovery for automatic Genie PC local network discovery.
 */
class MDNSDiscoveryManager(context: Context) {

    private val nsdManager = context.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val SERVICE_TYPE = "_genie._tcp."

    private val _discoveredPc = MutableStateFlow<DiscoveredPC?>(null)
    val discoveredPc: StateFlow<DiscoveredPC?> = _discoveredPc.asStateFlow()

    private val _isSearching = MutableStateFlow(false)
    val isSearching: StateFlow<Boolean> = _isSearching.asStateFlow()

    private var discoveryListener: NsdManager.DiscoveryListener? = null

    fun startDiscovery() {
        if (_isSearching.value) return
        _isSearching.value = true

        discoveryListener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(regType: String) {}

            override fun onServiceFound(service: NsdServiceInfo) {
                if (service.serviceType.contains("_genie._tcp")) {
                    nsdManager.resolveService(service, object : NsdManager.ResolveListener {
                        override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {}

                        override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
                            val host: InetAddress = serviceInfo.host
                            val ip = host.hostAddress ?: "192.168.1.100"
                            val port = serviceInfo.port
                            _discoveredPc.value = DiscoveredPC(
                                serviceName = serviceInfo.serviceName,
                                hostAddress = ip,
                                port = port
                            )
                        }
                    })
                }
            }

            override fun onServiceLost(service: NsdServiceInfo) {}
            override fun onDiscoveryStopped(serviceType: String) { _isSearching.value = false }
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) { nsdManager.stopServiceDiscovery(this) }
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) { nsdManager.stopServiceDiscovery(this) }
        }

        try {
            nsdManager.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, discoveryListener)
        } catch (e: Exception) {
            e.printStackTrace()
            _isSearching.value = false
        }
    }

    fun stopDiscovery() {
        discoveryListener?.let {
            try {
                nsdManager.stopServiceDiscovery(it)
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
        discoveryListener = null
        _isSearching.value = false
    }
}
