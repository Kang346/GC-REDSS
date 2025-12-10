import React from 'react'
import { Card, Typography, Descriptions, Tag, Divider } from 'antd'
import { CloseOutlined } from '@ant-design/icons'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts'
import { usePropertyStore } from '../store/propertyStore'
import { Property } from '../types'

const { Title, Text } = Typography

interface PropertyDetailProps {
  property: Property
}

const PropertyDetail: React.FC<PropertyDetailProps> = ({ property }) => {
  const { setSelectedProperty } = usePropertyStore()

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'green'
    if (score >= 0.6) return 'orange'
    return 'red'
  }

  // Prepare data for radar chart
  const radarData = [
    {
      category: 'Price',
      score: (property.SCORE_PRICE_SCORE || 0) * 100,
      fullMark: 100,
    },
    {
      category: 'Commute',
      score: (property.SCORE_COMMUTE_SCORE || 0) * 100,
      fullMark: 100,
    },
    {
      category: 'Life',
      score: (property.SCORE_LIFE_SCORE || 0) * 100,
      fullMark: 100,
    },
    {
      category: 'Size',
      score: (property.SCORE_PROPERTY_SIZE_SCORE || 0) * 100,
      fullMark: 100,
    },
    {
      category: 'Bedrooms',
      score: (property.SCORE_BEDROOMS_SCORE || 0) * 100,
      fullMark: 100,
    },
    {
      category: 'Bathrooms',
      score: (property.SCORE_BATHROOMS_SCORE || 0) * 100,
      fullMark: 100,
    },
  ]

  const barData = [
    { name: 'Price', score: (property.SCORE_PRICE_SCORE || 0) * 100 },
    { name: 'Commute', score: (property.SCORE_COMMUTE_SCORE || 0) * 100 },
    { name: 'Life', score: (property.SCORE_LIFE_SCORE || 0) * 100 },
    { name: 'Size', score: (property.SCORE_PROPERTY_SIZE_SCORE || 0) * 100 },
    { name: 'Bedrooms', score: (property.SCORE_BEDROOMS_SCORE || 0) * 100 },
    { name: 'Bathrooms', score: (property.SCORE_BATHROOMS_SCORE || 0) * 100 },
  ]

  return (
    <Card
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Property Details</span>
          <CloseOutlined
            onClick={() => setSelectedProperty(null)}
            style={{ cursor: 'pointer', fontSize: '16px' }}
          />
        </div>
      }
      style={{ maxHeight: '90vh', overflow: 'auto' }}
    >
      <Title level={4} style={{ marginBottom: 16 }}>
        {property.ADDRESS}
      </Title>

      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="Price">
          <Text strong style={{ color: '#1890ff', fontSize: '18px' }}>
            ${property.PRICE.toLocaleString()}
          </Text>
          {property.PRICE_PER_SQFT && (
            <Text type="secondary" style={{ marginLeft: 8 }}>
              (${property.PRICE_PER_SQFT.toFixed(0)}/sqft)
            </Text>
          )}
        </Descriptions.Item>
        
        <Descriptions.Item label="Overall Score">
          <Tag color={getScoreColor(property.SCORE_S_SCORE)} style={{ fontSize: '16px', padding: '4px 12px' }}>
            {(property.SCORE_S_SCORE * 100).toFixed(1)}%
          </Tag>
        </Descriptions.Item>
        
        <Descriptions.Item label="Bedrooms">{property.BEDS}</Descriptions.Item>
        <Descriptions.Item label="Bathrooms">{property.BATH}</Descriptions.Item>
        {property.PROPERTYSQFT && (
          <Descriptions.Item label="Square Feet">
            {property.PROPERTYSQFT.toLocaleString()} sqft
          </Descriptions.Item>
        )}
        {property.BOROUGH && (
          <Descriptions.Item label="Borough">{property.BOROUGH}</Descriptions.Item>
        )}
        {property.TYPE && (
          <Descriptions.Item label="Type">{property.TYPE}</Descriptions.Item>
        )}
      </Descriptions>

      <Divider>Score Breakdown</Divider>

      <div style={{ marginBottom: 24 }}>
        <Text strong>Radar Chart</Text>
        <ResponsiveContainer width="100%" height={250}>
          <RadarChart data={radarData}>
            <PolarGrid />
            <PolarAngleAxis dataKey="category" />
            <PolarRadiusAxis angle={90} domain={[0, 100]} />
            <Radar
              name="Score"
              dataKey="score"
              stroke="#1890ff"
              fill="#1890ff"
              fillOpacity={0.6}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      <div>
        <Text strong>Bar Chart</Text>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={barData}>
            <XAxis dataKey="name" />
            <YAxis domain={[0, 100]} />
            <Tooltip />
            <Bar dataKey="score" fill="#1890ff" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <Divider>Location</Divider>
      <Text type="secondary" style={{ fontSize: '12px' }}>
        Lat: {property.LATITUDE.toFixed(4)}, Lng: {property.LONGITUDE.toFixed(4)}
      </Text>
    </Card>
  )
}

export default PropertyDetail



