import axios from 'axios'
import { SearchParams, ApiResponse } from '../types'

// API URL - defaults to 5002 (common fallback when 5000/5001 are busy)
// Update .env file or set VITE_API_URL environment variable to change
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5002'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const propertyApi = {
  /**
   * Score properties based on search criteria
   */
  scoreProperties: async (params: SearchParams): Promise<ApiResponse> => {
    const response = await api.post<ApiResponse>('/api/score', params)
    return response.data
  },

  /**
   * Get configuration
   */
  getConfig: async () => {
    const response = await api.get('/api/config')
    return response.data
  },

  /**
   * Update scoring weights
   */
  updateWeights: async (weights: SearchParams['weights']) => {
    const response = await api.post('/api/config/weights', { weights })
    return response.data
  },

  /**
   * Health check
   */
  healthCheck: async () => {
    const response = await api.get('/health')
    return response.data
  },

  /**
   * Geocode address to get coordinates
   */
  geocodeAddress: async (address: string) => {
    const response = await api.post('/api/geocode', { address })
    return response.data
  },
}

export default api

