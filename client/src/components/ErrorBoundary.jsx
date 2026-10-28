import React from 'react'
import './ErrorBoundary.css'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-boundary-content">
            <h1>Something went wrong</h1>
            <p>The application encountered an unexpected error. Please refresh the page or try again later.</p>
            <button
              type="button"
              className="error-boundary-button"
              onClick={() => window.location.reload()}
            >
              Reload page
            </button>
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <pre className="error-boundary-details">{this.state.error.toString()}</pre>
            )}
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default ErrorBoundary
