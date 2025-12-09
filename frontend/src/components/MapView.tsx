import React, { useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polygon, useMap } from 'react-leaflet'
import L from 'leaflet'
import { usePropertyStore } from '../store/propertyStore'
import 'leaflet/dist/leaflet.css'

// Fix for default marker icons in React-Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

// Custom marker icon based on score
const createScoreIcon = (score: number) => {
  const color = score >= 0.8 ? 'green' : score >= 0.6 ? 'orange' : 'red'
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="
      background-color: ${color};
      width: 20px;
      height: 20px;
      border-radius: 50%;
      border: 2px solid white;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    "></div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  })
}

// Component to fit map bounds to markers
const MapBounds: React.FC<{ properties: any[] }> = ({ properties }) => {
  const map = useMap()
  
  useEffect(() => {
    if (properties.length > 0) {
      const bounds = L.latLngBounds(
        properties.map(p => [p.LATITUDE, p.LONGITUDE] as [number, number])
      )
      map.fitBounds(bounds, { padding: [50, 50] })
    }
  }, [properties, map])
  
  return null
}

const MapView: React.FC = () => {
  const { 
    properties, 
    setSelectedProperty, 
    searchParams,
    commuteCircles,
    workLocation: storeWorkLocation
  } = usePropertyStore()
  
  // NYC center coordinates
  const nycCenter: [number, number] = [40.7128, -74.0060]
  
  // Use work location from store, or fallback to geocoding
  const workLocation: [number, number] | null = storeWorkLocation 
    ? [storeWorkLocation.latitude, storeWorkLocation.longitude]
    : null

  const handleMarkerClick = (property: any) => {
    setSelectedProperty(property)
  }

  // Convert GeoJSON coordinates to Leaflet format [lat, lon][]
  const convertGeoJsonToLeaflet = (coords: number[][][]): [number, number][] => {
    // GeoJSON format: [[[lon, lat], ...]]
    // Leaflet format: [[lat, lon], ...]
    if (coords && coords.length > 0 && coords[0].length > 0) {
      return coords[0].map((coord: number[]) => [coord[1], coord[0]] as [number, number])
    }
    return []
  }

  return (
    <MapContainer
      center={workLocation || nycCenter}
      zoom={workLocation ? 12 : 11}
      style={{ height: '100%', width: '100%' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      
      {/* Show work location marker */}
      {workLocation && (
        <Marker position={workLocation}>
          <Popup>
            <div>
              <strong>📍 Work Location</strong>
              <br />
              {searchParams?.work_address}
              {searchParams?.commute_threshold && (
                <>
                  <br />
                  <small>Commute threshold: {searchParams.commute_threshold} minutes</small>
                </>
              )}
            </div>
          </Popup>
        </Marker>
      )}
      
      {/* Show commute circles (polygons) from API response */}
      {commuteCircles && Object.entries(commuteCircles).map(([mode, circle]) => {
        const positions = convertGeoJsonToLeaflet(circle.coordinates)
        if (positions.length === 0) return null
        
        // Color coding for different transport modes
        const modeColors: { [key: string]: { color: string; fillColor: string } } = {
          driving: { color: '#3388ff', fillColor: '#3388ff' },
          walking: { color: '#52c41a', fillColor: '#52c41a' },
          transit: { color: '#fa8c16', fillColor: '#fa8c16' },
          biking: { color: '#eb2f96', fillColor: '#eb2f96' },
        }
        
        const colors = modeColors[mode] || { color: '#3388ff', fillColor: '#3388ff' }
        
        return (
          <Polygon
            key={mode}
            positions={positions}
            pathOptions={{
              color: colors.color,
              fillColor: colors.fillColor,
              fillOpacity: 0.15,
              weight: 2,
            }}
          >
            <Popup>
              <div>
                <strong>{mode.charAt(0).toUpperCase() + mode.slice(1)} Commute Zone</strong>
                <br />
                <small>
                  {searchParams?.commute_threshold} minutes from {searchParams?.work_address}
                </small>
              </div>
            </Popup>
          </Polygon>
        )
      })}
      
      {/* Property markers */}
      {properties.map((property, index) => (
        <Marker
          key={index}
          position={[property.LATITUDE, property.LONGITUDE]}
          icon={createScoreIcon(property.SCORE_S_SCORE)}
          eventHandlers={{
            click: () => handleMarkerClick(property),
          }}
        >
          <Popup>
            <div style={{ minWidth: '200px' }}>
              <h3 style={{ margin: '0 0 8px 0', fontSize: '14px' }}>
                {property.ADDRESS}
              </h3>
              <p style={{ margin: '4px 0', fontSize: '12px' }}>
                <strong>Price:</strong> ${property.PRICE.toLocaleString()}
              </p>
              <p style={{ margin: '4px 0', fontSize: '12px' }}>
                <strong>Score:</strong> {(property.SCORE_S_SCORE * 100).toFixed(1)}%
              </p>
              <p style={{ margin: '4px 0', fontSize: '12px' }}>
                <strong>Beds/Bath:</strong> {property.BEDS}/{property.BATH}
              </p>
              <p style={{ margin: '4px 0', fontSize: '12px', color: '#666' }}>
                Click for details →
              </p>
            </div>
          </Popup>
        </Marker>
      ))}
      
      {/* Fit bounds to all properties */}
      <MapBounds properties={properties} />
    </MapContainer>
  )
}

export default MapView

