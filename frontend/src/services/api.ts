import axios from 'axios'
import { SearchParams, ApiResponse } from '../types'

// API URL - defaults to 5001 (5000 is often occupied by macOS AirPlay Receiver)
// Update .env file or set VITE_API_URL environment variable to change
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 300000, // 5 minutes timeout (for complex road network calculations in new locations)
})

// Add request interceptor
api.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    // Log error but don't crash the app
    if (error.code === 'ECONNREFUSED' || error.message.includes('Network Error')) {
      console.error('API server is not running or not accessible at', API_BASE_URL)
    } else {
      console.error('API Error:', error.message)
    }
    return Promise.reject(error)
  }
)

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

