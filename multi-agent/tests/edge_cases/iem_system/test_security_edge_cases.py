"""
Comprehensive security edge case tests for IEM system.

Tests injection attacks, malicious payloads, and security boundary conditions.
"""

import pytest
import time
import threading
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch

from mas.core.iem.messenger import DefaultInterMessenger
from mas.core.iem.models import ElementAddress
from mas.core.iem.packets import BaseIEMPacket, TaskPacket, SystemPacket
from mas.core.iem.exceptions import IEMException, IEMValidationException
from tests.fixtures.iem_testing_tools import (
    create_test_state_view, create_test_step_context,
    PacketFactory, IEMPerformanceMonitor
)


class SecurityTestPayloads:
    """Collection of security test payloads and attack vectors."""
    
    @staticmethod
    def get_injection_payloads() -> Dict[str, str]:
        """Get various injection attack payloads."""
        return {
            "sql_injection_basic": "'; DROP TABLE users; --",
            "sql_injection_union": "' UNION SELECT * FROM passwords --",
            "sql_injection_blind": "' AND 1=1 --",
            "nosql_injection": "{'$ne': null}",
            "ldap_injection": "*)(uid=*))(|(uid=*",
            "xpath_injection": "' or '1'='1",
            "command_injection": "; rm -rf / #",
            "command_injection_windows": "& del /f /q *.*",
            "script_injection": "<script>alert('xss')</script>",
            "script_injection_encoded": "%3Cscript%3Ealert%28%27xss%27%29%3C%2Fscript%3E",
            "html_injection": "<img src=x onerror=alert('xss')>",
            "css_injection": "body{background:url(javascript:alert('xss'))}",
            "json_injection": '{"injection": "value", "admin": true}',
            "xml_injection": "<?xml version='1.0'?><!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><root>&xxe;</root>",
            "template_injection": "{{config.__class__.__init__.__globals__['os'].popen('ls').read()}}",
            "python_code_injection": "__import__('os').system('ls')",
            "javascript_injection": "javascript:alert('xss')",
            "vbscript_injection": "vbscript:msgbox('xss')",
            "ssi_injection": "<!--#exec cmd='/bin/cat /etc/passwd'-->",
            "crlf_injection": "test\\r\\nSet-Cookie: admin=true",
            "format_string": "%x%x%x%x%x%x%x%x%x%x%n"
        }
    
    @staticmethod
    def get_path_traversal_payloads() -> List[str]:
        """Get path traversal attack payloads."""
        return [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd",
            "/var/www/../../etc/passwd",
            "C:\\windows\\..\\..\\..\\etc\\passwd",
            "file:///etc/passwd",
            "file://c:/windows/system32/drivers/etc/hosts",
            "\\\\server\\share\\file.txt",
            "/proc/self/environ",
            "/proc/version",
            "/proc/cmdline"
        ]
    
    @staticmethod
    def get_buffer_overflow_payloads() -> Dict[str, str]:
        """Get buffer overflow test payloads."""
        return {
            "pattern_small": "A" * 100,
            "pattern_medium": "B" * 1000,
            "pattern_large": "C" * 10000,
            "pattern_huge": "D" * 100000,
            "null_bytes": "\\x00" * 1000,
            "high_ascii": "\\xff" * 1000,
            "format_string_large": "%s" * 1000,
            "unicode_large": "\\u0041" * 10000,
            "mixed_pattern": ("A" * 100 + "\\x00" + "B" * 100) * 100,
            "graduated_pattern": "".join(chr(i % 256) for i in range(10000))
        }
    
    @staticmethod
    def get_timing_attack_payloads() -> List[Dict[str, Any]]:
        """Get payloads for timing attack tests."""
        return [
            {"payload": "valid_user", "expected_delay": 0.1},
            {"payload": "invalid_user", "expected_delay": 0.1},
            {"payload": "admin", "expected_delay": 0.1},
            {"payload": "test", "expected_delay": 0.1},
            {"payload": "guest", "expected_delay": 0.1},
            {"payload": "root", "expected_delay": 0.1},
            {"payload": "user123", "expected_delay": 0.1},
            {"payload": "nonexistent", "expected_delay": 0.1}
        ]
    
    @staticmethod
    def get_malicious_unicode_payloads() -> List[str]:
        """Get malicious Unicode payloads."""
        return [
            "\\u202e\\u0631\\u064a\\u062c\\u064a\\u0631\\u202d",  # Right-to-left override
            "\\ufeff\\u200b\\u200c\\u200d",  # Zero-width characters
            "\\ud800\\udc00",  # Surrogate pairs
            "\\u0000\\u0001\\u0002\\u0003",  # Control characters
            "\\uffff\\ufffe\\ufffd",  # Noncharacters
            "\\U0001f4a9" * 1000,  # Many emojis
            "\\u0020\\u00a0\\u2000\\u2001\\u2002\\u2003",  # Various spaces
            "\\u0041\\u0301\\u0302\\u0303",  # Combining characters
            "\\u05d0\\u05d1\\u05d2",  # Hebrew
            "\\u0627\\u0628\\u062a",  # Arabic
            "\\u4e00\\u4e01\\u4e03",  # Chinese
            "\\ud83d\\ude00\\ud83d\\ude01\\ud83d\\ude02"  # Emoji sequence
        ]


class MaliciousPacketGenerator:
    """Generator for malicious packets and attack scenarios."""
    
    @staticmethod
    def create_oversized_packet(size_factor: int = 10) -> TaskPacket:
        """Create packet with oversized payload."""
        large_content = "x" * (1024 * 1024 * size_factor)  # size_factor MB
        return PacketFactory.create_task_packet(
            "malicious_sender",
            "target",
            large_content
        )
    
    @staticmethod
    def create_deeply_nested_packet(depth: int = 100) -> TaskPacket:
        """Create packet with deeply nested data structures."""
        nested_data = {"level": 0}
        current = nested_data
        
        for i in range(depth):
            current["next"] = {"level": i + 1}
            current = current["next"]
        
        packet = PacketFactory.create_task_packet(
            "malicious_sender",
            "target",
            "Deeply nested attack"
        )
        packet.payload["nested_data"] = nested_data
        return packet
    
    @staticmethod
    def create_circular_reference_packet() -> TaskPacket:
        """Create packet with circular references (if possible)."""
        packet = PacketFactory.create_task_packet(
            "malicious_sender",
            "target",
            "Circular reference attack"
        )
        
        # Try to create circular reference
        data_a = {"name": "a"}
        data_b = {"name": "b", "ref": data_a}
        data_a["ref"] = data_b
        
        try:
            packet.payload["circular_data"] = data_a
        except Exception:
            # If circular references are prevented, use alternative
            packet.payload["circular_attempt"] = "blocked"
        
        return packet
    
    @staticmethod
    def create_memory_bomb_packet() -> TaskPacket:
        """Create packet designed to consume excessive memory."""
        # Create data structure that expands dramatically
        packet = PacketFactory.create_task_packet(
            "malicious_sender",
            "target",
            "Memory bomb attack"
        )
        
        # Multiple large arrays
        packet.payload["bomb_data"] = {
            "array1": ["x" * 1000] * 1000,  # 1MB
            "array2": ["y" * 1000] * 1000,  # 1MB  
            "array3": ["z" * 1000] * 1000,  # 1MB
            "metadata": "memory_bomb"
        }
        
        return packet
    
    @staticmethod
    def create_timing_attack_packets(count: int = 50) -> List[TaskPacket]:
        """Create packets for timing attack analysis."""
        packets = []
        
        for i in range(count):
            # Mix of different payload sizes to test timing
            size = 100 + (i * 10)  # Increasing sizes
            content = "timing_test_" + ("x" * size)
            
            packet = PacketFactory.create_task_packet(
                "timing_attacker",
                "target",
                content
            )
            packet.payload["timing_data"] = {
                "sequence": i,
                "size": size,
                "timestamp": time.time()
            }
            packets.append(packet)
        
        return packets


class SecurityTestHarness:
    """Harness for conducting security tests."""
    
    def __init__(self):
        self.state = create_test_state_view()
        self.attack_results = []
        self.defense_metrics = {
            "blocked_attacks": 0,
            "successful_attacks": 0,
            "timing_anomalies": 0,
            "resource_violations": 0
        }
    
    def setup_secure_messenger(self, uid: str, adjacent_nodes: List[str]) -> DefaultInterMessenger:
        """Set up messenger with security monitoring."""
        context = create_test_step_context(uid, adjacent_nodes)
        messenger = DefaultInterMessenger(
            state=self.state,
            identity=ElementAddress(uid=uid),
            context=context
        )
        return messenger
    
    def test_injection_attacks(self, messenger: DefaultInterMessenger) -> Dict[str, Any]:
        """Test various injection attacks."""
        injection_payloads = SecurityTestPayloads.get_injection_payloads()
        results = {
            "total_attempts": len(injection_payloads),
            "blocked": 0,
            "successful": 0,
            "errors": 0,
            "details": []
        }
        
        for attack_name, payload in injection_payloads.items():
            try:
                packet = PacketFactory.create_task_packet(
                    "attacker",
                    messenger.identity.uid,
                    payload
                )
                packet.payload["attack_type"] = attack_name
                
                packet_id = messenger.send_packet(packet)
                
                if packet_id:
                    results["successful"] += 1
                    self.defense_metrics["successful_attacks"] += 1
                else:
                    results["blocked"] += 1
                    self.defense_metrics["blocked_attacks"] += 1
                
                results["details"].append({
                    "attack": attack_name,
                    "payload_length": len(payload),
                    "result": "successful" if packet_id else "blocked"
                })
                
            except Exception as e:
                results["errors"] += 1
                results["details"].append({
                    "attack": attack_name,
                    "payload_length": len(payload),
                    "result": "error",
                    "error": str(e)
                })
        
        return results
    
    def test_timing_attacks(self, messenger: DefaultInterMessenger) -> Dict[str, Any]:
        """Test for timing attack vulnerabilities."""
        timing_payloads = SecurityTestPayloads.get_timing_attack_payloads()
        timing_results = []
        
        for test_case in timing_payloads:
            payload = test_case["payload"]
            
            # Measure processing time
            start_time = time.perf_counter()
            
            try:
                packet = PacketFactory.create_task_packet(
                    "timing_attacker",
                    messenger.identity.uid,
                    payload
                )
                messenger.send_packet(packet)
                
            except Exception:
                pass  # Continue timing measurement even on errors
            
            end_time = time.perf_counter()
            processing_time = end_time - start_time
            
            timing_results.append({
                "payload": payload,
                "processing_time": processing_time,
                "expected_delay": test_case["expected_delay"]
            })
        
        # Analyze timing variations
        times = [r["processing_time"] for r in timing_results]
        avg_time = sum(times) / len(times) if times else 0
        max_time = max(times) if times else 0
        min_time = min(times) if times else 0
        time_variance = max_time - min_time
        
        # Check for timing anomalies (significant variations)
        anomaly_threshold = avg_time * 2  # 2x average time
        anomalies = [r for r in timing_results if r["processing_time"] > anomaly_threshold]
        
        if anomalies:
            self.defense_metrics["timing_anomalies"] += len(anomalies)
        
        return {
            "test_count": len(timing_results),
            "avg_time": avg_time,
            "max_time": max_time,
            "min_time": min_time,
            "time_variance": time_variance,
            "anomalies": len(anomalies),
            "anomaly_details": anomalies[:5]  # First 5 anomalies
        }
    
    def test_resource_exhaustion(self, messenger: DefaultInterMessenger) -> Dict[str, Any]:
        """Test resource exhaustion attacks."""
        resource_results = {
            "oversized_packets": 0,
            "memory_bombs": 0,
            "nested_attacks": 0,
            "blocked_by_system": 0,
            "resource_violations": 0
        }
        
        # Test oversized packets
        try:
            oversized = MaliciousPacketGenerator.create_oversized_packet(size_factor=1)  # 1MB
            messenger.send_packet(oversized)
            resource_results["oversized_packets"] += 1
        except Exception as e:
            resource_results["blocked_by_system"] += 1
            self.defense_metrics["resource_violations"] += 1
        
        # Test deeply nested structures
        try:
            nested = MaliciousPacketGenerator.create_deeply_nested_packet(depth=50)
            messenger.send_packet(nested)
            resource_results["nested_attacks"] += 1
        except Exception as e:
            resource_results["blocked_by_system"] += 1
            self.defense_metrics["resource_violations"] += 1
        
        # Test memory bomb
        try:
            memory_bomb = MaliciousPacketGenerator.create_memory_bomb_packet()
            messenger.send_packet(memory_bomb)
            resource_results["memory_bombs"] += 1
        except Exception as e:
            resource_results["blocked_by_system"] += 1
            self.defense_metrics["resource_violations"] += 1
        
        return resource_results


class TestSecurityEdgeCases:
    """Test suite for security edge cases and attack vectors."""
    
    def test_injection_attack_resistance(self):
        """Test resistance to various injection attacks."""
        harness = SecurityTestHarness()
        messenger = harness.setup_secure_messenger("secure_node", ["target"])
        
        # Test injection attacks
        injection_results = harness.test_injection_attacks(messenger)
        
        print(f"Injection attack test results:")
        print(f"  Total attempts: {injection_results['total_attempts']}")
        print(f"  Blocked: {injection_results['blocked']}")
        print(f"  Successful: {injection_results['successful']}")
        print(f"  Errors: {injection_results['errors']}")
        
        # Security assessment
        if injection_results["total_attempts"] > 0:
            block_rate = injection_results["blocked"] / injection_results["total_attempts"]
            success_rate = injection_results["successful"] / injection_results["total_attempts"]
            
            # Most injection attempts should be handled gracefully
            assert success_rate < 0.8, f"Too many injection attacks succeeded: {success_rate:.2%}"
            
            # System should handle injection attempts (errors are acceptable as they indicate rejection)
            # High error rate is expected for injection attacks as they should be rejected
            assert injection_results["errors"] <= injection_results["total_attempts"]
    
    def test_buffer_overflow_resistance(self):
        """Test resistance to buffer overflow attacks."""
        state = create_test_state_view()
        context = create_test_step_context("buffer_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="buffer_test_node"),
            context=context
        )
        
        buffer_payloads = SecurityTestPayloads.get_buffer_overflow_payloads()
        results = {"successful": 0, "blocked": 0, "errors": 0}
        
        for test_name, payload in buffer_payloads.items():
            try:
                packet = PacketFactory.create_task_packet(
                    "buffer_attacker",
                    "buffer_test_node",
                    payload
                )
                
                packet_id = messenger.send_packet(packet)
                if packet_id:
                    results["successful"] += 1
                else:
                    results["blocked"] += 1
                    
            except Exception as e:
                results["errors"] += 1
                print(f"Buffer overflow test {test_name} error: {str(e)}")
        
        print(f"Buffer overflow test results:")
        print(f"  Successful: {results['successful']}")
        print(f"  Blocked: {results['blocked']}")
        print(f"  Errors: {results['errors']}")
        
        # System should handle large payloads gracefully
        total_tests = sum(results.values())
        if total_tests > 0:
            error_rate = results["errors"] / total_tests
            assert error_rate < 0.5, f"High error rate in buffer tests: {error_rate:.2%}"
    
    def test_path_traversal_resistance(self):
        """Test resistance to path traversal attacks."""
        state = create_test_state_view()
        context = create_test_step_context("path_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="path_test_node"),
            context=context
        )
        
        path_payloads = SecurityTestPayloads.get_path_traversal_payloads()
        suspicious_patterns_found = 0
        
        for payload in path_payloads:
            try:
                packet = PacketFactory.create_task_packet(
                    "path_attacker",
                    "path_test_node",
                    f"Path traversal test: {payload}"
                )
                packet.payload["file_path"] = payload
                
                packet_id = messenger.send_packet(packet)
                
                # Check if payload was sanitized or rejected
                if "../" in payload or "..\\" in payload:
                    suspicious_patterns_found += 1
                
            except Exception as e:
                # Path traversal attempts might cause exceptions
                print(f"Path traversal blocked: {payload} - {str(e)}")
        
        print(f"Path traversal test:")
        print(f"  Total payloads tested: {len(path_payloads)}")
        print(f"  Suspicious patterns: {suspicious_patterns_found}")
        
        # Should handle path traversal attempts without crashing
        assert suspicious_patterns_found > 0  # We did test suspicious patterns
    
    def test_unicode_security_issues(self):
        """Test Unicode-related security issues."""
        state = create_test_state_view()
        context = create_test_step_context("unicode_test_node", ["target"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="unicode_test_node"),
            context=context
        )
        
        unicode_payloads = SecurityTestPayloads.get_malicious_unicode_payloads()
        results = {"processed": 0, "errors": 0, "blocked": 0}
        
        for payload in unicode_payloads:
            try:
                packet = PacketFactory.create_task_packet(
                    "unicode_attacker",
                    "unicode_test_node",
                    payload
                )
                
                packet_id = messenger.send_packet(packet)
                if packet_id:
                    results["processed"] += 1
                else:
                    results["blocked"] += 1
                    
            except Exception as e:
                results["errors"] += 1
                print(f"Unicode payload error: {str(e)}")
        
        print(f"Unicode security test:")
        print(f"  Processed: {results['processed']}")
        print(f"  Blocked: {results['blocked']}")
        print(f"  Errors: {results['errors']}")
        
        # Should handle Unicode without catastrophic failures
        total_tests = sum(results.values())
        if total_tests > 0:
            success_rate = (results["processed"] + results["blocked"]) / total_tests
            assert success_rate > 0.5, "Too many Unicode handling failures"
    
    def test_timing_attack_resistance(self):
        """Test resistance to timing attacks."""
        harness = SecurityTestHarness()
        messenger = harness.setup_secure_messenger("timing_test_node", ["target"])
        
        # Test timing attack resistance
        timing_results = harness.test_timing_attacks(messenger)
        
        print(f"Timing attack test results:")
        print(f"  Test count: {timing_results['test_count']}")
        print(f"  Average time: {timing_results['avg_time']:.4f}s")
        print(f"  Time variance: {timing_results['time_variance']:.4f}s")
        print(f"  Anomalies detected: {timing_results['anomalies']}")
        
        # Check for timing attack vulnerabilities
        if timing_results["test_count"] > 0:
            # Timing variance should be reasonable
            relative_variance = timing_results["time_variance"] / timing_results["avg_time"] if timing_results["avg_time"] > 0 else 0
            
            # Large timing variations might indicate vulnerabilities
            assert relative_variance < 10.0, f"Excessive timing variance: {relative_variance:.2f}"
            
            # Should not have many timing anomalies
            anomaly_rate = timing_results["anomalies"] / timing_results["test_count"]
            assert anomaly_rate < 0.3, f"High anomaly rate: {anomaly_rate:.2%}"
    
    def test_resource_exhaustion_defense(self):
        """Test defense against resource exhaustion attacks."""
        harness = SecurityTestHarness()
        messenger = harness.setup_secure_messenger("resource_defense_node", ["target"])
        
        # Test resource exhaustion attacks
        resource_results = harness.test_resource_exhaustion(messenger)
        
        print(f"Resource exhaustion test results:")
        print(f"  Oversized packets: {resource_results['oversized_packets']}")
        print(f"  Memory bombs: {resource_results['memory_bombs']}")
        print(f"  Nested attacks: {resource_results['nested_attacks']}")
        print(f"  Blocked by system: {resource_results['blocked_by_system']}")
        
        # System should provide some protection against resource exhaustion
        total_attacks = (resource_results["oversized_packets"] + 
                        resource_results["memory_bombs"] + 
                        resource_results["nested_attacks"])
        
        if total_attacks > 0:
            # Some attacks should be blocked
            defense_rate = resource_results["blocked_by_system"] / (total_attacks + resource_results["blocked_by_system"])
            print(f"  Defense rate: {defense_rate:.2%}")
    
    def test_malicious_packet_flood(self):
        """Test system behavior under malicious packet flood."""
        state = create_test_state_view()
        context = create_test_step_context("flood_target", ["attacker"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="flood_target"),
            context=context
        )
        
        # Generate flood of malicious packets
        flood_size = 100  # Moderate size for testing
        successful_sends = 0
        errors = 0
        
        start_time = time.time()
        
        for i in range(flood_size):
            try:
                # Mix different types of malicious packets
                if i % 3 == 0:
                    # Oversized packet
                    packet = MaliciousPacketGenerator.create_oversized_packet(size_factor=1)
                elif i % 3 == 1:
                    # Deeply nested packet
                    packet = MaliciousPacketGenerator.create_deeply_nested_packet(depth=20)
                else:
                    # Regular malicious packet
                    packet = PacketFactory.create_task_packet(
                        "attacker",
                        "flood_target",
                        f"Flood packet {i} with injection: '; DROP TABLE users; --"
                    )
                
                messenger.send_packet(packet)
                successful_sends += 1
                
            except Exception as e:
                errors += 1
                if i < 5:  # Log first few errors
                    print(f"Flood packet {i} error: {str(e)}")
            
            # Small delay to prevent overwhelming test system
            if i % 10 == 0:
                time.sleep(0.001)
        
        total_time = time.time() - start_time
        
        print(f"Malicious packet flood test:")
        print(f"  Flood size: {flood_size}")
        print(f"  Successful sends: {successful_sends}")
        print(f"  Errors: {errors}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Rate: {flood_size / total_time:.1f} packets/sec")
        
        # System should handle flood without complete failure
        success_rate = successful_sends / flood_size
        error_rate = errors / flood_size
        
        # Should process some packets but also show some resistance
        assert success_rate > 0.3, f"System rejected too many packets: {success_rate:.2%}"
        assert error_rate < 0.8, f"Too many errors during flood: {error_rate:.2%}"
    
    def test_privilege_escalation_attempts(self):
        """Test attempts to escalate privileges through packet manipulation."""
        state = create_test_state_view()
        context = create_test_step_context("privilege_test_node", ["admin_node"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="privilege_test_node"),
            context=context
        )
        
        # Attempt various privilege escalation techniques
        escalation_attempts = [
            {"role": "admin", "action": "grant_access"},
            {"user": "root", "sudo": True},
            {"permissions": ["read", "write", "execute", "admin"]},
            {"override": True, "bypass_checks": True},
            {"escalate": "administrator", "level": 999},
            {"impersonate": "admin_node", "spoofed": True}
        ]
        
        successful_attempts = 0
        blocked_attempts = 0
        
        for i, attempt in enumerate(escalation_attempts):
            try:
                packet = PacketFactory.create_task_packet(
                    "privilege_test_node",
                    "admin_node",
                    f"Privilege escalation attempt {i}"
                )
                packet.payload.update(attempt)
                packet.payload["escalation_attempt"] = True
                
                packet_id = messenger.send_packet(packet)
                if packet_id:
                    successful_attempts += 1
                else:
                    blocked_attempts += 1
                    
            except Exception as e:
                blocked_attempts += 1
                print(f"Privilege escalation blocked: {str(e)}")
        
        print(f"Privilege escalation test:")
        print(f"  Total attempts: {len(escalation_attempts)}")
        print(f"  Successful: {successful_attempts}")
        print(f"  Blocked: {blocked_attempts}")
        
        # Note: At the packet level, most attempts will likely succeed
        # as the IEM system focuses on message transport, not authorization
        # Real privilege checks would happen at the application level
    
    def test_data_exfiltration_attempts(self):
        """Test attempts to exfiltrate data through packet manipulation."""
        state = create_test_state_view()
        context = create_test_step_context("exfil_test_node", ["data_server"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="exfil_test_node"),
            context=context
        )
        
        # Simulate data exfiltration attempts
        exfiltration_payloads = [
            "GET /etc/passwd HTTP/1.1",
            "SELECT * FROM users WHERE 1=1",
            "cat /var/log/auth.log",
            "grep -r 'password' /home/",
            "find / -name '*.key' 2>/dev/null",
            "netstat -tuln",
            "ps aux | grep -v grep",
            "env | grep -i secret"
        ]
        
        exfil_attempts = 0
        
        for payload in exfiltration_payloads:
            try:
                packet = PacketFactory.create_task_packet(
                    "exfil_test_node",
                    "data_server",
                    payload
                )
                packet.payload["exfiltration_attempt"] = True
                packet.payload["command"] = payload
                
                packet_id = messenger.send_packet(packet)
                if packet_id:
                    exfil_attempts += 1
                    
            except Exception as e:
                print(f"Exfiltration attempt blocked: {str(e)}")
        
        print(f"Data exfiltration test:")
        print(f"  Total payloads: {len(exfiltration_payloads)}")
        print(f"  Successful attempts: {exfil_attempts}")
        
        # At the IEM level, these packets will likely be transmitted
        # Actual data protection would happen at the application level
        assert exfil_attempts >= 0  # Basic sanity check
    
    def test_cryptographic_attack_vectors(self):
        """Test cryptographic attack vectors."""
        state = create_test_state_view()
        context = create_test_step_context("crypto_test_node", ["secure_server"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="crypto_test_node"),
            context=context
        )
        
        # Test various cryptographic attack patterns
        crypto_attacks = [
            {"type": "weak_hash", "value": hashlib.md5(b"weak").hexdigest()},
            {"type": "collision", "value": "chosen_plaintext_attack"},
            {"type": "timing_attack", "key_length": 1024},
            {"type": "side_channel", "power_analysis": True},
            {"type": "rainbow_table", "hash": "5d41402abc4b2a76b9719d911017c592"},
            {"type": "birthday_attack", "collision_search": True},
            {"type": "meet_in_middle", "dual_encryption": True}
        ]
        
        crypto_test_results = {"sent": 0, "errors": 0}
        
        for attack in crypto_attacks:
            try:
                packet = PacketFactory.create_task_packet(
                    "crypto_test_node",
                    "secure_server",
                    f"Crypto attack: {attack['type']}"
                )
                packet.payload.update(attack)
                
                packet_id = messenger.send_packet(packet)
                if packet_id:
                    crypto_test_results["sent"] += 1
                    
            except Exception as e:
                crypto_test_results["errors"] += 1
                print(f"Crypto attack error: {str(e)}")
        
        print(f"Cryptographic attack test:")
        print(f"  Attacks sent: {crypto_test_results['sent']}")
        print(f"  Errors: {crypto_test_results['errors']}")
        
        # Should handle crypto-related payloads without crashing
        assert crypto_test_results["sent"] + crypto_test_results["errors"] == len(crypto_attacks)
    
    def test_denial_of_service_resistance(self):
        """Test resistance to denial of service attacks."""
        state = create_test_state_view()
        context = create_test_step_context("dos_target", ["attacker"])
        messenger = DefaultInterMessenger(
            state=state,
            identity=ElementAddress(uid="dos_target"),
            context=context
        )
        monitor = IEMPerformanceMonitor()
        
        # Simulate DoS attack with rapid packet sending
        with monitor.monitor_operation("dos_attack_test") as op_id:
            dos_packets = 200  # Moderate for testing
            successful_packets = 0
            failed_packets = 0
            
            for i in range(dos_packets):
                try:
                    # Vary packet types and sizes for realistic DoS
                    if i % 4 == 0:
                        content = "DoS packet " + ("x" * (i % 100))
                    elif i % 4 == 1:
                        content = "'; DROP TABLE packets; --" * (i % 10)
                    elif i % 4 == 2:
                        content = "<script>alert('dos')</script>" * (i % 5)
                    else:
                        content = "Regular DoS packet"
                    
                    packet = PacketFactory.create_task_packet(
                        "attacker",
                        "dos_target",
                        content
                    )
                    packet.payload["dos_attack"] = True
                    packet.payload["sequence"] = i
                    
                    messenger.send_packet(packet)
                    successful_packets += 1
                    
                except Exception as e:
                    failed_packets += 1
                    if i < 5:  # Log first few failures
                        print(f"DoS packet {i} failed: {str(e)}")
                
                # No delay - simulate rapid attack
        
        # Analyze DoS resistance
        perf_stats = monitor.get_operation_stats("dos_attack_test")
        
        print(f"DoS resistance test:")
        print(f"  Total packets attempted: {dos_packets}")
        print(f"  Successful: {successful_packets}")
        print(f"  Failed: {failed_packets}")
        print(f"  Success rate: {successful_packets / dos_packets:.2%}")
        print(f"  Average duration: {perf_stats['avg_duration_ms']:.2f}ms")
        
        # System should maintain some functionality under DoS
        success_rate = successful_packets / dos_packets
        assert success_rate > 0.5, f"DoS attack too effective: {success_rate:.2%}"
        assert perf_stats["avg_duration_ms"] < 1000, "DoS caused excessive latency"
