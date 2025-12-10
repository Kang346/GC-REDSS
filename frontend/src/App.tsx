import { Layout } from 'antd'
import SearchForm from './components/SearchForm'
import MapView from './components/MapView'
import PropertyList from './components/PropertyList'
import PropertyDetail from './components/PropertyDetail'
import ErrorBoundary from './components/ErrorBoundary'
import { usePropertyStore } from './store/propertyStore'
import './App.css'

const { Header, Content, Sider } = Layout

const App: React.FC = () => {
  const { selectedProperty } = usePropertyStore()

  return (
    <ErrorBoundary>
      <Layout style={{ height: '100vh' }}>
        <Header style={{ 
          background: '#001529', 
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          padding: '0 24px'
        }}>
          <h1 style={{ margin: 0, fontSize: '20px' }}>
            🏠 GC-REDSS - Real Estate Decision Support System
          </h1>
        </Header>
        
        <Layout>
          <Sider 
            width={400} 
            style={{ 
              background: '#fff',
              overflow: 'auto',
              borderRight: '1px solid #f0f0f0'
            }}
          >
            <div style={{ padding: '16px' }}>
              <ErrorBoundary>
                <SearchForm />
              </ErrorBoundary>
              <ErrorBoundary>
                <PropertyList />
              </ErrorBoundary>
            </div>
          </Sider>
          
          <Content style={{ position: 'relative' }}>
            <ErrorBoundary>
              <MapView />
            </ErrorBoundary>
            {selectedProperty && (
              <div style={{
                position: 'absolute',
                top: 16,
                right: 16,
                width: 400,
                zIndex: 1000,
                background: '#fff',
                borderRadius: 8,
                boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
              }}>
                <ErrorBoundary>
                  <PropertyDetail property={selectedProperty} />
                </ErrorBoundary>
              </div>
            )}
          </Content>
        </Layout>
      </Layout>
    </ErrorBoundary>
  )
}

export default App



