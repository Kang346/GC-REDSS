import React from 'react'
import { List, Card, Typography, Tag, Empty, Alert } from 'antd'
import { usePropertyStore } from '../store/propertyStore'
import { Property } from '../types'

const { Text, Title } = Typography

const PropertyList: React.FC = () => {
  const { properties, selectedProperty, setSelectedProperty, loading, error } = usePropertyStore()

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'green'
    if (score >= 0.6) return 'orange'
    return 'red'
  }

  if (loading) {
    return <Card><Text>Loading properties...</Text></Card>
  }

  if (error) {
    return (
      <Card>
        <Alert
          message="Error"
          description={error}
          type="error"
          showIcon
          closable
          onClose={() => usePropertyStore.getState().setError(null)}
        />
      </Card>
    )
  }

  if (!properties || properties.length === 0) {
    return (
      <Card>
        <Empty description="No properties found. Search to get started!" />
      </Card>
    )
  }

  return (
    <Card title={`📋 Properties (${properties.length})`}>
      <List
        dataSource={properties}
        renderItem={(property: Property, index: number) => (
          <List.Item
            style={{
              cursor: 'pointer',
              backgroundColor: selectedProperty?.ADDRESS === property.ADDRESS ? '#e6f7ff' : 'transparent',
              padding: '12px',
              marginBottom: '8px',
              borderRadius: '4px',
              border: selectedProperty?.ADDRESS === property.ADDRESS ? '2px solid #1890ff' : '1px solid #f0f0f0',
            }}
            onClick={() => setSelectedProperty(property)}
          >
            <div style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '8px' }}>
                <Title level={5} style={{ margin: 0, fontSize: '14px' }}>
                  #{index + 1} {property.ADDRESS.split(',')[0]}
                </Title>
                <Tag color={getScoreColor(property.SCORE_S_SCORE)}>
                  {(property.SCORE_S_SCORE * 100).toFixed(0)}%
                </Tag>
              </div>
              
              <div style={{ display: 'flex', gap: '12px', marginBottom: '4px' }}>
                <Text strong style={{ color: '#1890ff' }}>
                  ${property.PRICE.toLocaleString()}
                </Text>
                <Text type="secondary">
                  {property.BEDS} bed / {property.BATH} bath
                </Text>
                {property.PROPERTYSQFT && (
                  <Text type="secondary">
                    {property.PROPERTYSQFT.toLocaleString()} sqft
                  </Text>
                )}
              </div>
              
              {property.BOROUGH && (
                <Tag color="blue" style={{ marginTop: '4px' }}>
                  {property.BOROUGH}
                </Tag>
              )}
            </div>
          </List.Item>
        )}
      />
    </Card>
  )
}

export default PropertyList



