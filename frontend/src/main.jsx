import React from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './styles.css'
import Home from './pages/Home'
import Results from './pages/Results'

const router = createBrowserRouter([
	{ path: '/', element: <Home /> },
	{ path: '/results/:year/:gp', element: <Results /> },
])

createRoot(document.getElementById('root')).render(
	<React.StrictMode>
		<RouterProvider router={router} />
	</React.StrictMode>
)
