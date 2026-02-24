import React from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider, Outlet } from 'react-router-dom'
import './styles.css'
import Home from './pages/Home'
import Predict from './pages/Predict'
import Compare from './pages/Compare'
import Winner from './pages/Winner'
import Navbar from './components/Navbar'

function Shell() {
	return (
		<div className="min-h-screen bg-black text-white">
			<Navbar />
			<div className="max-w-6xl mx-auto px-4 py-6">
				<Outlet />
			</div>
		</div>
	)
}

const router = createBrowserRouter([
	{
		path: '/',
		element: <Shell />, children: [
			{ path: '/', element: <Home /> },
			{ path: '/predict', element: <Predict /> },
			{ path: '/compare', element: <Compare /> },
			{ path: '/winner', element: <Winner /> },
		]
	}
])

createRoot(document.getElementById('root')).render(
	<React.StrictMode>
		<RouterProvider router={router} />
	</React.StrictMode>
)
