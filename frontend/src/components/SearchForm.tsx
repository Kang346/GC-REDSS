import React, { useState, useEffect } from 'react'
import { Form, Input, Button, Slider, Card, Divider, Checkbox, InputNumber, Row, Col, Space } from 'antd'
import { SearchOutlined, EnvironmentOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { propertyApi } from '../services/api'
import { usePropertyStore, defaultWeights } from '../store/propertyStore'
import { SearchParams } from '../types'

const SearchForm: React.FC = () => {
  const [form] = Form.useForm()
  const { 
    setProperties, 
    setLoading, 
    setError, 
    setSearchParams, 
    setCommuteCircles, 
    setWorkLocation, 
    loading,
    mapClickMode,
    setMapClickMode,
    pendingWorkLocation,
    setPendingWorkLocation
  } = usePropertyStore()
  const [weights, setWeights] = useState(defaultWeights)
  const [transportModes, setTransportModes] = useState<string[]>(['driving'])

  useEffect(() => {
    // Load default config
    propertyApi.getConfig()
      .then((config) => {
        if (config.default_weights) {
          setWeights(config.default_weights)
          form.setFieldsValue({ weights: config.default_weights })
        }
      })
      .catch((error) => {
        // Silently fail if API is not available, use default weights
        console.warn('Failed to load config, using defaults:', error)
      })
    
    // Listen for map location selection
    const handleMapLocationSelected = (event: CustomEvent) => {
      const { address, latitude, longitude } = event.detail
      form.setFieldsValue({ work_address: address })
      setPendingWorkLocation({ latitude, longitude })
    }
    
    window.addEventListener('mapLocationSelected', handleMapLocationSelected as EventListener)
    
    return () => {
      window.removeEventListener('mapLocationSelected', handleMapLocationSelected as EventListener)
    }
  }, [form, setPendingWorkLocation])

  const onFinish = async (values: any) => {
    setLoading(true)
    setError(null)

    const params: SearchParams = {
      work_address: values.work_address,
      commute_threshold: values.commute_threshold || 30,
      life_threshold: values.life_threshold || 15,
      top_n: values.top_n || 50,
      price_min: values.price_min,
      price_max: values.price_max,
      fast_mode: true,  // Enable fast mode for quick response (~1-2 seconds)
      transport_modes: transportModes.length ? transportModes : ['driving'],
      weights: weights,
    }

    try {
      const response = await propertyApi.scoreProperties(params)
      
      // Defensive check: ensure properties array exists
      if (response && response.properties) {
        setProperties(Array.isArray(response.properties) ? response.properties : [])
      } else {
        setProperties([])
      }
      
      setSearchParams(params)
      
      // Store commute circles and work location for map display
      if (response && response.commute_circles) {
        setCommuteCircles(response.commute_circles)
      } else {
        setCommuteCircles(null)
      }
      if (response && response.work_location) {
        setWorkLocation(response.work_location)
      } else {
        setWorkLocation(null)
      }
    } catch (error: any) {
      let errorMessage = 'Failed to fetch properties'
      
      if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
        errorMessage = `Cannot connect to API server. Please ensure the backend API is running on ${import.meta.env.VITE_API_URL || 'http://localhost:5001'}. Check the browser console for details.`
      } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        errorMessage = `Request timed out. The calculation is taking longer than expected. This may happen for new locations. Please try: 1) Reducing commute threshold, 2) Selecting only one transport mode, or 3) Waiting a bit longer and trying again.`
      } else if (error.response?.data?.error) {
        errorMessage = error.response.data.error
      } else if (error.message) {
        errorMessage = error.message
      }
      
      setError(errorMessage)
      console.error('Search Error:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleWeightChange = (key: string, value: number) => {
    const newWeights = { ...weights, [key]: value / 100 }
    setWeights(newWeights)
    form.setFieldsValue({ weights: newWeights })
  }

  return (
    <Card title="🔍 Search Properties" style={{ marginBottom: 16 }}>
      <Form
        form={form}
        layout="vertical"
        onFinish={onFinish}
        initialValues={{
          work_address: 'Times Square, New York, NY',
          commute_threshold: 30,
          life_threshold: 15,
          top_n: 50,
          transport_modes: ['driving'],
          weights: defaultWeights,
        }}
      >
        <Form.Item
          label="Work Address"
          name="work_address"
          rules={[{ required: true, message: 'Please enter work address' }]}
        >
          <Space.Compact style={{ width: '100%' }}>
            <Input 
              placeholder="e.g., Times Square, New York, NY" 
              style={{ flex: 1 }}
            />
            <Button
              type={mapClickMode ? "primary" : "default"}
              icon={<EnvironmentOutlined />}
              onClick={() => setMapClickMode(!mapClickMode)}
              danger={mapClickMode}
            >
              {mapClickMode ? 'Cancel' : 'Pick on Map'}
            </Button>
          </Space.Compact>
          {pendingWorkLocation && (
            <div style={{ marginTop: 8 }}>
              <Space>
                <span style={{ fontSize: '12px', color: '#666' }}>
                  📍 Location selected: {pendingWorkLocation.latitude.toFixed(6)}, {pendingWorkLocation.longitude.toFixed(6)}
                </span>
                <Button
                  size="small"
                  type="primary"
                  icon={<CheckOutlined />}
                  onClick={() => {
                    // Use the pending location
                    setWorkLocation(pendingWorkLocation)
                    setPendingWorkLocation(null)
                    setMapClickMode(false)
                  }}
                >
                  Use This Location
                </Button>
                <Button
                  size="small"
                  icon={<CloseOutlined />}
                  onClick={() => {
                    setPendingWorkLocation(null)
                    setMapClickMode(false)
                  }}
                >
                  Cancel
                </Button>
              </Space>
            </div>
          )}
          {mapClickMode && (
            <div style={{ marginTop: 4 }}>
              <small style={{ color: '#1890ff' }}>
                💡 Click anywhere on the map to select work location
              </small>
            </div>
          )}
        </Form.Item>

        <Form.Item label="Commute Threshold (minutes)" name="commute_threshold">
          <Slider min={10} max={60} marks={{ 10: '10', 30: '30', 60: '60' }} />
        </Form.Item>

        <Form.Item label="Life Accessibility Threshold (minutes)" name="life_threshold">
          <Slider min={5} max={30} marks={{ 5: '5', 15: '15', 30: '30' }} />
        </Form.Item>

        <Form.Item label="Number of Results" name="top_n">
          <Slider min={10} max={100} marks={{ 10: '10', 50: '50', 100: '100' }} />
        </Form.Item>

        <Divider>Price Filter</Divider>

        <Form.Item label="Price Range ($)">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="price_min" noStyle>
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="Min Price"
                  min={0}
                  formatter={(value) => value ? `$ ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : ''}
                  parser={(value) => {
                    const parsed = value?.replace(/\$\s?|(,*)/g, '') || ''
                    return parsed ? (parseFloat(parsed) as any) : undefined
                  }}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="price_max" noStyle>
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="Max Price"
                  min={0}
                  formatter={(value) => value ? `$ ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : ''}
                  parser={(value) => {
                    const parsed = value?.replace(/\$\s?|(,*)/g, '') || ''
                    return parsed ? (parseFloat(parsed) as any) : undefined
                  }}
                />
              </Form.Item>
            </Col>
          </Row>
        </Form.Item>

        <Form.Item label="Transport Modes" name="transport_modes">
          <Checkbox.Group
            options={[
              { label: 'Driving', value: 'driving' },
              { label: 'Walking', value: 'walking' },
              { label: 'Transit', value: 'transit' },
              { label: 'Biking', value: 'biking' },
              { label: 'Subway', value: 'subway' },
            ]}
            value={transportModes}
            onChange={(vals) => setTransportModes(vals as string[])}
          />
        </Form.Item>

        <Divider>Scoring Weights</Divider>

        <Form.Item label={`Price: ${(weights.price * 100).toFixed(0)}%`}>
          <Slider
            min={0}
            max={100}
            value={weights.price * 100}
            onChange={(value) => handleWeightChange('price', value)}
          />
        </Form.Item>

        <Form.Item label={`Commute Time: ${(weights.commute_time * 100).toFixed(0)}%`}>
          <Slider
            min={0}
            max={100}
            value={weights.commute_time * 100}
            onChange={(value) => handleWeightChange('commute_time', value)}
          />
        </Form.Item>

        <Form.Item label={`Life Accessibility: ${(weights.life_accessibility * 100).toFixed(0)}%`}>
          <Slider
            min={0}
            max={100}
            value={weights.life_accessibility * 100}
            onChange={(value) => handleWeightChange('life_accessibility', value)}
          />
        </Form.Item>

        <Form.Item label={`Property Size: ${(weights.property_size * 100).toFixed(0)}%`}>
          <Slider
            min={0}
            max={100}
            value={weights.property_size * 100}
            onChange={(value) => handleWeightChange('property_size', value)}
          />
        </Form.Item>

        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            icon={<SearchOutlined />}
            block
            loading={loading}
          >
            Search Properties
          </Button>
        </Form.Item>
      </Form>
    </Card>
  )
}

export default SearchForm

