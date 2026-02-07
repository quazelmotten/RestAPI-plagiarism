"""
Simple S3-like storage implementation from scratch.
Stores files in a local directory structure with bucket organization.
"""

import hashlib
import os
from pathlib import Path
from typing import BinaryIO, Optional
import uuid
from datetime import datetime


class S3Storage:
    """Simple S3-like storage implementation using local filesystem."""
    
    def __init__(self, base_path: str = "/app/s3_storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_bucket_path(self, bucket_name: str) -> Path:
        """Get path to bucket directory."""
        bucket_path = self.base_path / bucket_name
        bucket_path.mkdir(exist_ok=True)
        return bucket_path
    
    def _generate_key(self, filename: str) -> str:
        """Generate a unique S3 key for the file."""
        timestamp = datetime.utcnow().strftime("%Y/%m/%d")
        unique_id = str(uuid.uuid4())[:8]
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        return f"{timestamp}/{unique_id}_{safe_filename}"
    
    def upload_file(
        self, 
        bucket_name: str, 
        file_data: BinaryIO, 
        filename: str
    ) -> dict:
        """
        Upload a file to S3 storage.
        
        Args:
            bucket_name: Name of the bucket
            file_data: File-like object containing the file data
            filename: Original filename
            
        Returns:
            dict with 'key', 'path', and 'hash' of the stored file
        """
        bucket_path = self._get_bucket_path(bucket_name)
        key = self._generate_key(filename)
        
        # Create subdirectory structure
        file_path = bucket_path / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Read file content and calculate hash
        content = file_data.read()
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Write file to storage
        with open(file_path, 'wb') as f:
            f.write(content)
        
        return {
            "key": key,
            "path": str(file_path),
            "hash": file_hash,
            "bucket": bucket_name,
            "filename": filename,
            "size": len(content)
        }
    
    def download_file(self, bucket_name: str, key: str) -> Optional[bytes]:
        """Download a file from S3 storage."""
        file_path = self.base_path / bucket_name / key
        
        if not file_path.exists():
            return None
        
        with open(file_path, 'rb') as f:
            return f.read()
    
    def file_exists(self, bucket_name: str, key: str) -> bool:
        """Check if a file exists in storage."""
        file_path = self.base_path / bucket_name / key
        return file_path.exists()
    
    def delete_file(self, bucket_name: str, key: str) -> bool:
        """Delete a file from storage."""
        file_path = self.base_path / bucket_name / key
        
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def list_bucket(self, bucket_name: str) -> list:
        """List all files in a bucket."""
        bucket_path = self._get_bucket_path(bucket_name)
        files = []
        
        for file_path in bucket_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(bucket_path)
                files.append({
                    "key": str(relative_path),
                    "path": str(file_path),
                    "size": file_path.stat().st_size
                })
        
        return files


# Global S3 storage instance
s3_storage = S3Storage()
