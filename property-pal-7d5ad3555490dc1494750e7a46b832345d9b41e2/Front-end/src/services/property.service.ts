import { api } from '@/lib/api';
import { PropertyAdapter } from '@/adapters/property.adapter';
import { PropertyDTO, PaginatedDTO } from '@/lib/contracts/property.contract';

export const PropertyService = {

  async getAll(params: Record<string, unknown> = {}): Promise<PaginatedDTO<PropertyDTO>> {
    const backendResponse = await api.properties.list(params);
    return PropertyAdapter.toPaginatedDTO(backendResponse);
  },

  async getById(id: string): Promise<PropertyDTO> {
    const backendProperty = await api.properties.get(id);
    return PropertyAdapter.toDTO(backendProperty);
  },

  async create(data: Partial<PropertyDTO>): Promise<PropertyDTO> {
    const backendData = PropertyAdapter.fromDTO(data);
    const result = await api.properties.create(backendData as any);
    return PropertyAdapter.toDTO(result);
  },

  async update(id: string, data: Partial<PropertyDTO>): Promise<PropertyDTO> {
    const backendData = PropertyAdapter.fromDTO(data);
    const result = await api.properties.update(id, backendData as any);
    return PropertyAdapter.toDTO(result);
  },

  async delete(id: string): Promise<void> {
    await api.properties.delete(id);
  },

  async markSold(id: string): Promise<PropertyDTO> {
    const result = await api.properties.markSold(id);
    return PropertyAdapter.toDTO(result);
  },

  async botSearch(params: Record<string, unknown> = {}): Promise<PropertyDTO[]> {
    const results = await api.bot.search(params);
    return PropertyAdapter.toDTOList(results);
  },
};