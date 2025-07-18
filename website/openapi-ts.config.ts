import {defineConfig} from '@hey-api/openapi-ts';

// Use localhost for OpenAPI generation during development
const OPENAPI_URL = 'http://localhost:8000/openapi.json';

export default defineConfig({
   input: OPENAPI_URL,
   output: 'src/generated',
   plugins: ['@hey-api/client-fetch'],
});