import React, { useState, useEffect } from 'react'
import { Form, Input, Button, Slider, Card, Space, Typography, Divider } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { propertyApi } from '../services/api'
import { usePropertyStore, defaultWeights } from '../store/propertyStore'
import { SearchParams } from '../types'

const { Title } = Typography

const SearchForm: React.FC = () => {
  const [form] = Form.useForm()
  const { setProperties, setLoading, setError, setSearchParams, loading } = usePropertyStore()
  const [weights, setWeights] = useState(defaultWeights)

  useEffect(() => {
    // Load default config
    propertyApi.getConfig().then((config) => {
      if (config.default_weights) {
        setWeights(config.default_weights)
        form.setFieldsValue({ weights: config.default_weights })
      }
    })
  }, [form])

  const onFinish = async (values: any) => {
    setLoading(true)
    setError(null)

    const params: SearchParams = {
      work_address: values.work_address,
      commute_threshold: values.commute_threshold || 30,
      life_threshold: values.life_threshold || 15,
      top_n: values.top_n || 20,
      fast_mode: true,  // Enable fast mode for quick response (~1-2 seconds)
      transport_modes: ['driving'],  // Default to driving only for speed
      weights: weights,
    }

    try {
      const response = await propertyApi.scoreProperties(params)
      setProperties(response.properties)
      setSearchParams(params)
    } catch (error: any) {
      setError(error.response?.data?.error || 'Failed to fetch properties')
      console.error('Error:', error)
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
          top_n: 20,
          weights: defaultWeights,
        }}
      >
        <Form.Item
          label="Work Address"
          name="work_address"
          rules={[{ required: true, message: 'Please enter work address' }]}
        >
          <Input placeholder="e.g., Times Square, New York, NY" />
        </Form.Item>

        <Form.Item label="Commute Threshold (minutes)" name="commute_threshold">
          <Slider min={10} max={60} marks={{ 10: '10', 30: '30', 60: '60' }} />
        </Form.Item>

        <Form.Item label="Life Accessibility Threshold (minutes)" name="life_threshold">
          <Slider min={5} max={30} marks={{ 5: '5', 15: '15', 30: '30' }} />
        </Form.Item>

        <Form.Item label="Number of Results" name="top_n">
          <Slider min={10} max={50} marks={{ 10: '10', 20: '20', 50: '50' }} />
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

