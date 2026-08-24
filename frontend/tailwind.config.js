/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      spacing: {
        // slightly larger spacing scale (approx 1.25x) for more breathing room
        '1': '0.3125rem', // 5px
        '2': '0.625rem',  // 10px
        '3': '0.9375rem', // 15px
        '4': '1.25rem',   // 20px
        '6': '1.875rem',  // 30px
        '8': '2.5rem',    // 40px
        '10': '3.125rem', // 50px
        '12': '3.75rem',  // 60px
        '16': '5rem',     // 80px
      },
    },
  },
  plugins: [],
};
