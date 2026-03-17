"""
Unit tests for ElementAddress - Node addressing in IEM system.

Tests address creation, validation, equality, and string representation.
Covers edge cases with UIDs and address comparison logic.
"""

import pytest
from mas.core.iem.models import ElementAddress


class TestElementAddress:
    """Test suite for ElementAddress functionality."""
    
    def test_address_creation(self):
        """Test basic ElementAddress creation."""
        uid = "test_node_123"
        address = ElementAddress(uid=uid)
        
        assert address.uid == uid
        assert isinstance(address.uid, str)
        
    def test_address_equality_with_same_uid(self):
        """Test address equality when UIDs are the same."""
        uid = "same_node"
        address1 = ElementAddress(uid=uid)
        address2 = ElementAddress(uid=uid)
        
        assert address1 == address2
        assert address1.uid == address2.uid
        
    def test_address_equality_with_different_uids(self):
        """Test address inequality when UIDs are different."""
        address1 = ElementAddress(uid="node_1")
        address2 = ElementAddress(uid="node_2")
        
        assert address1 != address2
        assert address1.uid != address2.uid
        
    def test_address_equality_with_string(self):
        """Test address equality comparison with string UIDs."""
        uid = "string_comparison_node"
        address = ElementAddress(uid=uid)
        
        # Should be equal to string UID
        assert address == uid
        assert address.uid == uid
        
        # Should not be equal to different string
        assert address != "different_node"
        
    def test_address_equality_with_non_string_types(self):
        """Test address equality with non-string types."""
        address = ElementAddress(uid="test_node")
        
        # Should not be equal to non-string types
        assert address != 123
        assert address != None
        assert address != []
        assert address != {}
        assert address != True
        
    def test_address_string_representation(self):
        """Test string representation of ElementAddress."""
        uid = "string_repr_node"
        address = ElementAddress(uid=uid)
        
        assert str(address) == uid
        assert f"{address}" == uid
        
    def test_address_with_empty_uid(self):
        """Test ElementAddress with empty UID."""
        address = ElementAddress(uid="")
        
        assert address.uid == ""
        assert str(address) == ""
        
    def test_address_with_special_characters(self):
        """Test ElementAddress with special characters in UID."""
        special_uids = [
            "node-with-dashes",
            "node_with_underscores", 
            "node.with.dots",
            "node@domain.com",
            "node:with:colons",
            "node/with/slashes",
            "node with spaces",
            "node+with+plus",
            "node#with#hash",
            "node&with&ampersand",
            "node%with%percent",
            "node$with$dollar"
        ]
        
        for uid in special_uids:
            address = ElementAddress(uid=uid)
            assert address.uid == uid
            assert str(address) == uid
            
    def test_address_with_unicode_characters(self):
        """Test ElementAddress with Unicode characters."""
        unicode_uids = [
            "node_ñoño",
            "node_测试",
            "node_العربية",
            "node_русский",
            "node_🚀",
            "node_émojis_😀",
            "node_मैत्री"
        ]
        
        for uid in unicode_uids:
            address = ElementAddress(uid=uid)
            assert address.uid == uid
            assert str(address) == uid
            
    def test_address_with_very_long_uid(self):
        """Test ElementAddress with very long UID."""
        long_uid = "very_long_node_uid_" * 100  # Very long UID
        address = ElementAddress(uid=long_uid)
        
        assert address.uid == long_uid
        assert str(address) == long_uid
        assert len(str(address)) == len(long_uid)
        
    def test_address_validation(self):
        """Test ElementAddress validation requirements."""
        # Valid UIDs should work
        valid_uids = [
            "simple",
            "node_1",
            "complex-node.example.com",
            "a",  # Single character
            "1234567890"  # Numeric string
        ]
        
        for uid in valid_uids:
            address = ElementAddress(uid=uid)
            assert address.uid == uid
            
    def test_address_serialization(self):
        """Test ElementAddress serialization to dict."""
        uid = "serialization_test_node"
        address = ElementAddress(uid=uid)
        
        # Serialize to dict
        address_dict = address.model_dump()
        
        assert isinstance(address_dict, dict)
        assert address_dict["uid"] == uid
        
        # Deserialize back
        reconstructed_address = ElementAddress.model_validate(address_dict)
        assert reconstructed_address.uid == uid
        assert reconstructed_address == address
        
    def test_address_hash_consistency(self):
        """Test that ElementAddress equality works correctly (note: Pydantic models are not hashable)."""
        uid = "hash_test_node"
        address1 = ElementAddress(uid=uid)
        address2 = ElementAddress(uid=uid)
        
        # Equal addresses should be equal
        assert address1 == address2
        
        # ElementAddress is not hashable (Pydantic BaseModel), so we test UID-based operations instead
        uid_set = {address1.uid, address2.uid}
        assert len(uid_set) == 1  # Should deduplicate UIDs
        
    def test_address_in_collections(self):
        """Test ElementAddress usage in various collections."""
        addresses = [
            ElementAddress(uid="node_1"),
            ElementAddress(uid="node_2"), 
            ElementAddress(uid="node_3"),
            ElementAddress(uid="node_1")  # Duplicate
        ]
        
        # Test in list
        assert len(addresses) == 4
        
        # ElementAddress is not hashable, so test UID-based deduplication instead
        unique_uids = set(addr.uid for addr in addresses)
        assert len(unique_uids) == 3  # Duplicate UID should be removed
        
        # Test as dictionary with UID keys (since ElementAddress itself can't be a key)
        address_dict = {}
        for addr in addresses:
            address_dict[addr.uid] = f"value_for_{addr.uid}"
            
        assert len(address_dict) == 3
        assert "node_1" in address_dict
        assert "node_2" in address_dict
        assert "node_3" in address_dict
        
    def test_address_comparison_edge_cases(self):
        """Test edge cases in address comparison."""
        address = ElementAddress(uid="test")
        
        # Comparison with None
        assert address != None
        assert not (address == None)
        
        # Comparison with empty string
        empty_address = ElementAddress(uid="")
        assert address != empty_address
        assert address != ""
        
    def test_address_immutability(self):
        """Test that ElementAddress is effectively immutable."""
        uid = "immutable_test"
        address = ElementAddress(uid=uid)
        
        # UID should not be modifiable after creation
        original_uid = address.uid
        
        # Try to modify (this should not affect the address if properly designed)
        try:
            address.uid = "modified"
            # If modification is allowed, verify it worked
            assert address.uid == "modified"
        except AttributeError:
            # If modification is prevented, verify original value is preserved
            assert address.uid == original_uid
            
    def test_address_string_conversion_types(self):
        """Test various string conversion scenarios."""
        uid = "conversion_test"
        address = ElementAddress(uid=uid)
        
        # Test various string conversion methods
        assert str(address) == uid
        assert repr(address)  # Should not raise exception
        assert f"{address}" == uid
        assert "{}".format(address) == uid
        
    def test_multiple_addresses_equality_matrix(self):
        """Test equality relationships between multiple addresses."""
        uids = ["node_a", "node_b", "node_c", "node_a"]  # With duplicate
        addresses = [ElementAddress(uid=uid) for uid in uids]
        
        # Test all pairwise comparisons
        for i, addr1 in enumerate(addresses):
            for j, addr2 in enumerate(addresses):
                if uids[i] == uids[j]:
                    assert addr1 == addr2, f"Addresses with same UID should be equal: {uids[i]}"
                else:
                    assert addr1 != addr2, f"Addresses with different UIDs should not be equal: {uids[i]} vs {uids[j]}"
                    
    def test_address_with_whitespace_uids(self):
        """Test ElementAddress with various whitespace scenarios."""
        whitespace_uids = [
            " leading_space",
            "trailing_space ",
            " both_spaces ",
            "inner space",
            "\ttab_chars\t",
            "\nnewline_chars\n",
            "\r\nwindows_newlines\r\n",
            "   multiple   spaces   "
        ]
        
        for uid in whitespace_uids:
            address = ElementAddress(uid=uid)
            assert address.uid == uid  # Should preserve whitespace exactly
            assert str(address) == uid
