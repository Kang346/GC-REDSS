export interface Property {
  ADDRESS: string
  PRICE: number
  BEDS: number
  BATH: number
  PROPERTYSQFT: number
  LATITUDE: number
  LONGITUDE: number
  SCORE_S_SCORE: number
  SCORE_PRICE_SCORE: number
  SCORE_COMMUTE_SCORE: number
  SCORE_LIFE_SCORE: number
  SCORE_PROPERTY_SIZE_SCORE?: number
  SCORE_BEDROOMS_SCORE?: number
  SCORE_BATHROOMS_SCORE?: number
  PRICE_PER_SQFT?: number
  BOROUGH?: string
  TYPE?: string
  [key: string]: any
}

export interface SearchParams {
  work_address: string
  commute_threshold: number
  life_threshold: number
  top_n: number
  fast_mode?: boolean  // Enable fast mode for quick response (~1-2 seconds)
  transport_modes?: string[]  // Transport modes to consider (default: ['driving'])
  weights: {
    price: number
    commute_time: number
    life_accessibility: number
    property_size: number
    bedrooms: number
    bathrooms: number
  }
}

export interface ApiResponse {
  status: string
  count: number
  properties: Property[]
}

