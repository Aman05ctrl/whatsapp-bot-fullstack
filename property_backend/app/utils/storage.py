import cloudinary
import cloudinary.uploader
from typing import Optional
from property_backend.app.config import settings

# Configure Cloudinary once (module level)
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

class CloudinaryStorage:
    """
    Cloudinary Storage utility for uploading property images
    """
    
    def upload_file(self, file_content: bytes, file_extension: str) -> Optional[str]:
        """
        Upload file to Cloudinary and return the URL
        
        Args:
            file_content: Binary file content
            file_extension: File extension (not used, kept for compatibility)
        
        Returns:
            Public URL of uploaded file or None if failed
        """
        try:
            response = cloudinary.uploader.upload(
                file_content,
                folder="real_estate_properties/properties",
                resource_type="image",
                use_filename=True,
                unique_filename=True
            )
            
            return response.get("secure_url")
            
        except Exception as e:
            print(f"Cloudinary upload error: {e}")
            return None
    
    def delete_file(self, file_url: str) -> bool:
        """
        Delete file from Cloudinary
        
        Args:
            file_url: Full Cloudinary URL of the file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate URL format
            if "/upload/" not in file_url:
                return False
            
            # Extract public_id from URL
            # Example: https://res.cloudinary.com/.../upload/v123/folder/file.jpg
            # Extract: folder/file
            public_id = file_url.split("/upload/")[1]
            
            # Remove file extension
            public_id = public_id.split(".")[0]
            
            # Remove version number (v123456789/) if present
            if "/" in public_id:
                parts = public_id.split("/")
                if parts[0].startswith("v") and parts[0][1:].isdigit():
                    public_id = "/".join(parts[1:])
            
            # Delete from Cloudinary
            result = cloudinary.uploader.destroy(public_id, resource_type="image")
            
            return result.get("result") == "ok"
            
        except Exception as e:
            print(f"Cloudinary delete error: {e}")
            return False


# Singleton instance - IMPORTANT: keep this name
storage = CloudinaryStorage()