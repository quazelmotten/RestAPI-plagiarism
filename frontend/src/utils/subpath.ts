const SUBPATH = import.meta.env.VITE_SUBPATH !== undefined ? import.meta.env.VITE_SUBPATH : 'plagitype';

export const getSubpath = () => SUBPATH;
export const getBasePath = () => SUBPATH ? `/${SUBPATH}` : '';
export const getApiPath = (path: string) => SUBPATH ? `/${SUBPATH}${path}` : path;
export default SUBPATH;
