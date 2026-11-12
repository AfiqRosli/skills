import { defineConfig } from "vitepress";

export default defineConfig({
  title: "{{PROJECT_NAME}} Docs",
  description: "{{PROJECT_NAME}} documentation",
  themeConfig: {
    nav: [
      { text: "Home", link: "/" },
    ],
    sidebar: [
      {
        text: "Guide",
        items: [
          { text: "Getting Started", link: "/getting-started" },
        ],
      },
    ],
  },
});
