import { PropertyDTO, ImageDTO, PaginatedDTO } from '@/lib/contracts/property.contract';
import { Property, PropertyImage } from '@/lib/api';

// ✅ Backend → Contract (what Lovable UI receives)
export const PropertyAdapter = {
  
  toDTO(backendProperty: Property): PropertyDTO {
    return {
      id: backendProperty.id,
      client_id: backendProperty.client_id,
      title: backendProperty.title,
      description: backendProperty.description,
      city: backendProperty.city,
      area: backendProperty.area,
      price: backendProperty.price,
      property_type: backendProperty.property_type,
      bhk: backendProperty.bhk,
      emi_available: backendProperty.emi_available,
      emi_amount: backendProperty.emi_amount,
      expected_roi: backendProperty.expected_roi,
      status: backendProperty.status,
      primaryImage: backendProperty.images?.find(img => img.is_primary)?.image_url 
                     || backendProperty.images?.[0]?.image_url,
      images: backendProperty.images?.map(this.imageToDTO),
      created_at: backendProperty.created_at,
      updated_at: backendProperty.updated_at,
    };
  },

  imageToDTO(backendImage: PropertyImage): ImageDTO {
    return {
      id: backendImage.id,
      image_url: backendImage.image_url,
      is_primary: backendImage.is_primary,
    };
  },

  // Contract → Backend (what gets sent to API)
  fromDTO(dto: Partial<PropertyDTO>): any {
    return {
      title: dto.title,
      description: dto.description,
      city: dto.city,
      area: dto.area,
      price: dto.price,
      property_type: dto.property_type,
      bhk: dto.bhk,
      emi_available: dto.emi_available,
      emi_amount: dto.emi_amount,
      expected_roi: dto.expected_roi,
    };
  },

  // Array transformations
  toDTOList(properties: Property[]): PropertyDTO[] {
    return properties.map(p => this.toDTO(p));
  },

  // Paginated response transformation
  toPaginatedDTO(backendResponse: { properties: Property[]; total: number }): PaginatedDTO<PropertyDTO> {
    return {
      items: this.toDTOList(backendResponse.properties),
      total: backendResponse.total,
    };
  },
};