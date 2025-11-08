/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        flag: {
          green: '#34d399',
          yellow: '#fbbf24',
          red: '#f87171'
        }
      }
    }
  },
  plugins: []
};
