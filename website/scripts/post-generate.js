const fs = require('fs');
const path = require('path');

const generatedDir = path.join(__dirname, '..', 'src', 'generated');
const typesFile = path.join(generatedDir, 'types.gen.ts');
const clientFile = path.join(generatedDir, 'client.gen.ts');

console.log('Post-processing generated types...');

// Process types.gen.ts if it exists
if (fs.existsSync(typesFile)) {
  let content = fs.readFileSync(typesFile, 'utf8');
  
  // Replace unknown with any for better TypeScript compatibility
  content = content.replace(/: unknown/g, ': any');
  
  // Add custom type unions and helpers only if they don't exist
  if (!content.includes('export type PalioDataUnion')) {
    const customTypes = `
// Custom type unions for better usability
export type PalioDataUnion = PalioData;
export type LeaderboardUnion = Leaderboard;
export type PalioGamesStatusUnion = PalioGamesStatus;

// Year-based data types
export type YearBasedPalioData = PalioData;
export type YearBasedLeaderboard = Leaderboard;
export type YearBasedPalioGamesStatus = PalioGamesStatus;

`;
    content = content + customTypes;
  }
  
  fs.writeFileSync(typesFile, content);
  console.log('✅ Post-processed types.gen.ts');
} else {
  console.log('⚠️  types.gen.ts not found, skipping type processing');
}

// Process client.gen.ts if it exists
if (fs.existsSync(clientFile)) {
  let content = fs.readFileSync(clientFile, 'utf8');
  
  // Inject API base URL configuration
  content = content.replace(
    /baseUrl: string/g,
    `baseUrl: process.env.REACT_APP_API_URL || 'http://localhost:8000'`
  );
  
  // Add authentication headers if needed
  const authHeader = `
// Add authentication headers
client.interceptors.request.use((request) => {
  // Add any authentication headers here if needed
  return request;
});
`;
  
  // Find a good place to inject the auth header (after client creation)
  if (content.includes('export const client')) {
    content = content.replace(
      /export const client[^;]*;/,
      `$&\n${authHeader}`
    );
  }
  
  fs.writeFileSync(clientFile, content);
  console.log('✅ Post-processed client.gen.ts');
} else {
  console.log('⚠️  client.gen.ts not found, skipping client processing');
}

// Process client utils for TypeScript compatibility
const utilsFile = path.join(generatedDir, 'client', 'utils.ts');
if (fs.existsSync(utilsFile)) {
  let content = fs.readFileSync(utilsFile, 'utf8');
  
  // Fix the iterator type issue
  content = content.replace(
    /for \(const \[key, value\] of iterator\) {/g,
    'for (const [key, value] of Array.from(iterator)) {'
  );
  
  fs.writeFileSync(utilsFile, content);
  console.log('✅ Post-processed client/utils.ts');
} else {
  console.log('⚠️  client/utils.ts not found, skipping utils processing');
}

console.log('Post-processing complete!');