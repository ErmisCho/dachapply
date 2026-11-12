import './task-365-missing.css' // throwaway: must fail the build
import{createRoot}from'react-dom/client';import{createBrowserRouter,RouterProvider}from'react-router-dom';import App from './App';import './index.css';
const router=createBrowserRouter([{path:'*',element:<App/>}]);
createRoot(document.getElementById('root')!).render(<RouterProvider router={router}/>);
