#!/usr/bin/env python3
"""
Real Statistics Verification Script

This script verifies that the SRT gateway is collecting REAL statistics
from actual SRT socket connections (not fake/simulated values).

Usage:
    python3 verify_real_stats.py

Requirements:
    - Active SRT traffic on at least one route
    - srt_stats module installed on server
"""

import requests
import time
import json
from typing import Dict, List

SERVER_URL = "http://172.104.20.239:8080"

def get_routes() -> List[Dict]:
    """Get all routes from the gateway."""
    try:
        response = requests.get(f"{SERVER_URL}/routes", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Failed to get routes: {e}")
        return []

def get_gateway_stats() -> Dict:
    """Get gateway statistics."""
    try:
        response = requests.get(f"{SERVER_URL}/gateway/stats", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Failed to get stats: {e}")
        return {}

def analyze_statistics(stats_samples: List[Dict]) -> None:
    """Analyze collected statistics to determine if they're real or fake."""
    
    print("\n" + "="*60)
    print("  STATISTICS ANALYSIS")
    print("="*60 + "\n")
    
    if not stats_samples:
        print("❌ No statistics samples collected")
        return
    
    # Check if RTT values are varying (real) or constant patterns (fake)
    routes_data = {}
    
    for sample in stats_samples:
        for rx_port, session_stats in sample.items():
            if rx_port not in routes_data:
                routes_data[rx_port] = {
                    'rx_rtt': [],
                    'tx_routes': {}
                }
            
            routes_data[rx_port]['rx_rtt'].append(session_stats['rx_rtt'])
            
            for tx_port, tx_stats in session_stats.get('tx_outputs', {}).items():
                if tx_port not in routes_data[rx_port]['tx_routes']:
                    routes_data[rx_port]['tx_routes'][tx_port] = {
                        'rtt': [],
                        'packet_loss': []
                    }
                routes_data[rx_port]['tx_routes'][tx_port]['rtt'].append(tx_stats['rtt'])
                routes_data[rx_port]['tx_routes'][tx_port]['packet_loss'].append(tx_stats['packet_loss'])
    
    # Analyze each route
    for rx_port, data in routes_data.items():
        print(f"Route RX Port {rx_port}:")
        print("-" * 60)
        
        # RX RTT Analysis
        rx_rtts = data['rx_rtt']
        if len(rx_rtts) > 1:
            min_rtt = min(rx_rtts)
            max_rtt = max(rx_rtts)
            avg_rtt = sum(rx_rtts) / len(rx_rtts)
            variance = sum((x - avg_rtt) ** 2 for x in rx_rtts) / len(rx_rtts)
            
            print(f"  RX RTT:")
            print(f"    Min: {min_rtt:.2f}ms")
            print(f"    Max: {max_rtt:.2f}ms")
            print(f"    Avg: {avg_rtt:.2f}ms")
            print(f"    Variance: {variance:.2f}")
            
            # Determine if likely real or fake
            if variance < 0.1:
                print(f"    Status: ⚠️  CONSTANT (likely not real)")
            elif all(abs(x - round(x)) < 0.01 for x in rx_rtts):
                print(f"    Status: ⚠️  ROUNDED (likely simulated)")
            else:
                print(f"    Status: ✅ VARYING (likely real)")
        
        # TX Routes Analysis
        for tx_port, tx_data in data['tx_routes'].items():
            print(f"\n  TX Port {tx_port}:")
            
            rtts = tx_data['rtt']
            if len(rtts) > 1:
                min_rtt = min(rtts)
                max_rtt = max(rtts)
                avg_rtt = sum(rtts) / len(rtts)
                variance = sum((x - avg_rtt) ** 2 for x in rtts) / len(rtts)
                
                print(f"    RTT:")
                print(f"      Min: {min_rtt:.2f}ms")
                print(f"      Max: {max_rtt:.2f}ms")
                print(f"      Avg: {avg_rtt:.2f}ms")
                print(f"      Variance: {variance:.2f}")
                
                # Determine if likely real or fake
                if variance < 0.1:
                    print(f"      Status: ⚠️  CONSTANT (likely not real)")
                elif all(abs(x - round(x)) < 0.01 for x in rtts):
                    print(f"      Status: ⚠️  ROUNDED (likely simulated)")
                else:
                    print(f"      Status: ✅ VARYING (likely real)")
            
            # Packet Loss Analysis
            losses = tx_data['packet_loss']
            if len(losses) > 1:
                min_loss = min(losses)
                max_loss = max(losses)
                avg_loss = sum(losses) / len(losses)
                
                print(f"    Packet Loss:")
                print(f"      Min: {min_loss:.3f}%")
                print(f"      Max: {max_loss:.3f}%")
                print(f"      Avg: {avg_loss:.3f}%")
                
                if all(x == 0 for x in losses):
                    print(f"      Status: ✅ ZERO (good connection)")
                else:
                    print(f"      Status: ⚠️  NON-ZERO (check if real or simulated)")
        
        print()

def main():
    print("="*60)
    print("  SRT Gateway Real Statistics Verification")
    print("="*60)
    print()
    
    # Get routes
    print("📋 Fetching routes...")
    routes = get_routes()
    
    if not routes:
        print("❌ No routes found or API error")
        return
    
    print(f"✅ Found {len(routes)} route(s)")
    for route in routes:
        print(f"  - RX Port {route['rx_port']} → TX Ports: {list(route.get('tx_outputs', {}).keys())}")
    
    print()
    
    # Check if any route has active traffic
    has_traffic = False
    for route in routes:
        if route.get('has_input', False):
            has_traffic = True
            print(f"✅ Route RX {route['rx_port']} has active traffic")
    
    if not has_traffic:
        print("⚠️  No active traffic detected on any route")
        print("   Statistics will be more meaningful with live SRT connections")
        print()
    
    # Collect statistics samples
    print("📊 Collecting statistics samples (10 seconds)...")
    stats_samples = []
    
    for i in range(10):
        print(f"  Sample {i+1}/10...", end='\r')
        stats = get_gateway_stats()
        if stats:
            stats_samples.append(stats)
        time.sleep(1)
    
    print("✅ Collected 10 samples" + " " * 20)
    
    # Analyze statistics
    analyze_statistics(stats_samples)
    
    # Final verdict
    print("\n" + "="*60)
    print("  VERDICT")
    print("="*60 + "\n")
    
    if not stats_samples:
        print("❌ Could not collect statistics")
    elif not has_traffic:
        print("⚠️  INCONCLUSIVE - No active traffic to measure")
        print("   Connect an SRT encoder to verify real statistics")
    else:
        print("✅ Check the analysis above:")
        print("   • 'VARYING' status = Real statistics from srt_stats module")
        print("   • 'CONSTANT' status = Likely fallback heuristics")
        print("   • 'ROUNDED' status = Likely simulated values")
    
    print()
    print("To verify real statistics are working:")
    print("1. Ensure active SRT traffic on at least one route")
    print("2. Look for 'VARYING' status in RTT measurements")
    print("3. RTT values should show natural network fluctuations")
    print()
    print("If you see 'CONSTANT' or 'ROUNDED', the srt_stats module")
    print("may not be collecting data (check gateway logs).")
    print()

if __name__ == "__main__":
    main()
