import React, { useEffect, useState } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet'
import L from 'leaflet'
import { usePropertyStore } from '../store/propertyStore'
import { propertyApi } from '../services/api'
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
  const { properties, selectedProperty, setSelectedProperty, searchParams } = usePropertyStore()
  const [workLocation, setWorkLocation] = useState<[number, number] | null>(null)
  
  // NYC center coordinates
  const nycCenter: [number, number] = [40.7128, -74.0060]

  // Geocode work address when search params change
  useEffect(() => {
    if (searchParams && searchParams.work_address) {
      propertyApi.geocodeAddress(searchParams.work_address)
        .then((result) => {
          setWorkLocation([result.latitude, result.longitude])
        })
        .catch((error) => {
          console.error('Geocoding error:', error)
          setWorkLocation(null)
        })
    } else {
      setWorkLocation(null)
    }
  }, [searchParams])

  const handleMarkerClick = (property: any) => {
    setSelectedProperty(property)
  }

  // Estimate radius in meters (rough conversion: 30 min commute ≈ 25km at 50km/h average)
  const getCommuteRadius = (minutes: number) => {
    // Rough estimate: 50 km/h average speed
    const km = (minutes / 60) * 50
    return km * 1000 // Convert to meters
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
            </div>
          </Popup>
        </Marker>
      )}
      
      {/* Show commute circle if work address is provided */}
      {workLocation && searchParams && (
        <Circle
          center={workLocation}
          radius={getCommuteRadius(searchParams.commute_threshold)}
          pathOptions={{
            color: '#3388ff',
            fillColor: '#3388ff',
            fillOpacity: 0.15,
            weight: 2,
          }}
        />
      )}
      
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

