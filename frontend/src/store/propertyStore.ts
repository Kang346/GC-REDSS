import { create } from 'zustand'
import { Property, SearchParams, CommuteCircle } from '../types'

interface PropertyState {
  properties: Property[]
  selectedProperty: Property | null
  loading: boolean
  error: string | null
  searchParams: SearchParams | null
  commuteCircles: { [mode: string]: CommuteCircle } | null
  workLocation: { latitude: number; longitude: number } | null
  
  setProperties: (properties: Property[]) => void
  setSelectedProperty: (property: Property | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setSearchParams: (params: SearchParams | null) => void
  setCommuteCircles: (circles: { [mode: string]: CommuteCircle } | null) => void
  setWorkLocation: (location: { latitude: number; longitude: number } | null) => void
}

const defaultWeights = {
  price: 0.3,
  commute_time: 0.25,
  life_accessibility: 0.15,
  property_size: 0.1,
  bedrooms: 0.1,
  bathrooms: 0.1,
}

export const usePropertyStore = create<PropertyState>((set) => ({
  properties: [],
  selectedProperty: null,
  loading: false,
  error: null,
  searchParams: null,
  commuteCircles: null,
  workLocation: null,

  setProperties: (properties) => set({ properties }),
  setSelectedProperty: (property) => set({ selectedProperty: property }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  setSearchParams: (params) => set({ searchParams: params }),
  setCommuteCircles: (circles) => set({ commuteCircles: circles }),
  setWorkLocation: (location) => set({ workLocation: location }),
}))

export { defaultWeights }

