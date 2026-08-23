/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        safety: {
          dark: '#F7F8FA',         // Soft off-white background
          card: '#FFFFFF',         // Solid white card surface
          border: '#E4E7EB',       // Subtle border
          textPrimary: '#111827',  // Near-black primary text
          textSecondary: '#6B7280',// Muted gray secondary text
          primary: '#0F766E',      // Deep teal-green accent
          success: '#16A34A',      // Safe status green
          warning: '#D97706',      // Warning status amber
          critical: '#DC2626',     // Risk status red
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Outfit', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
