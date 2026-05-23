# hub-ui

The frontend UI module for the **Scheduler Manager**.

## Tech Stack

This project is built using the following primary technologies:

- **Framework**: [React](https://react.dev/) (v19)
- **Language**: [TypeScript](https://www.typescriptlang.org/)
- **Build Tool**: [Vite](https://vitejs.dev/)
- **State Management**: [Zustand](https://github.com/pmndrs/zustand)
- **Routing**: [React Router](https://reactrouter.com/) (v7)
- **Data Fetching**: [TanStack Query](https://tanstack.com/query/latest) (v5)
- **UI Components & Styling**: [Ant Design (antd)](https://ant.design/) (v6)
- **Schema-Based Forms**: [React JSON Schema Form (RJSF)](https://rjsf-team.github.io/react-jsonschema-form/) (v6) with [Ant Design Theme](https://www.npmjs.com/package/@rjsf/antd)
- **API Client**: [@hey-api/openapi-ts](https://github.com/hey-api/openapi-ts) with [@hey-api/client-fetch](https://github.com/hey-api/client-fetch) (Modern OpenAPI-based client generation)

---

## Directory Structure

```
hub-ui/src/
├── api/                 # Custom API utilities and hooks
├── app/                 # Global application setup and providers
├── assets/              # Static assets (images, fonts, etc.)
├── components/          # Shared/common UI components
├── config/              # Application configuration (constants, env wrappers, etc.)
├── generated/           # Auto-generated code
│   └── api/             # OpenAPI-based API client
├── lib/                 # Third-party library configurations and wrappers (utils.ts, etc.)
├── stores/              # Global state management (Zustand)
├── utils/               # General utility helper functions
├── views/               # Page/view components (route-level views)
├── App.tsx              # Main App component and route configuration
└── main.tsx             # Application entry point
```

---

## Getting Started

### 1. Install Dependencies

```bash
npm install
```

### 2. Run the Development Server

```bash
npm run dev
```

### 3. Generate API Client

You can generate the type-safe API client using either of the following methods:

**Method A: Recommended (From the project root)**
Run the `just` command, which automatically exports the OpenAPI schema from the Python backend and generates the frontend client without requiring a running server:
```bash
just gen-ui-api
```

**Method B: Manual (From the `modules/hub-ui` directory)**
If you have a running backend server (JobRunner Hub at `http://localhost:8389` or specified by `VITE_API_BASE_URL`):
```bash
npm run gen:api
```

### 4. Build for Production

```bash
npm run build
```

### 5. Lint & Format Check

```bash
npm run lint
```

---

## Ant Design (antd) Integration Guide

This project leverages **Ant Design (antd) v6** as its primary design system and UI library. Ant Design v6 uses a modern **CSS-in-JS** styling engine, enabling dynamic, token-based runtime styling.

To maintain a consistent design system and high-quality user experience, follow the patterns and guidelines below.

### 1. Dynamic Theme Customization

The design system's theme is defined centrally using the `ConfigProvider` component. Customize tokens (like colors, border radiuses, and fonts) globally:

```tsx
// src/app/AppProvider.tsx (or main entry point)
import React from 'react';
import { ConfigProvider, theme } from 'antd';

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1677ff', // Brand primary color
          borderRadius: 6,         // Border radius for all components
          fontFamily: 'Inter, sans-serif',
        },
        algorithm: theme.defaultAlgorithm, // Supports theme.darkAlgorithm out of the box
      }}
    >
      {children}
    </ConfigProvider>
  );
};
```

### 2. Static Methods & Sub-components (Global Context)

Ant Design v6 components like `message`, `notification`, and `Modal` require a correct React context to inherit theme customizations and static styles. 

To ensure they function properly across the app, wrap the route/view tree inside an `<App>` component. You can then use the `App.useApp()` hook to access seamless, consistent static methods:

```tsx
import { Button, App } from 'antd';

export const MyComponent = () => {
  const { message, modal, notification } = App.useApp();

  const handleAction = () => {
    message.success('Task scheduled successfully!');
  };

  return <Button onClick={handleAction}>Schedule Task</Button>;
};
```

### 3. CSS-in-JS Design Tokens

Avoid hardcoding styling values (such as specific colors or border radiuses). Instead, use the `theme.useToken()` hook to access design system values. This guarantees consistent styling that dynamically updates when swapping themes (e.g., light to dark mode):

```tsx
import { theme } from 'antd';

export const CustomCard = ({ children }) => {
  const { token } = theme.useToken();

  return (
    <div
      style={{
        backgroundColor: token.colorBgContainer,
        color: token.colorText,
        border: `1px solid ${token.colorBorder}`,
        borderRadius: token.borderRadiusLG,
        padding: token.paddingMD,
      }}
    >
      {children}
    </div>
  );
};
```

### 4. Layout & Flex Guidelines

Use Ant Design's built-in layout components to maintain consistent spacing and responsiveness:
- **`Flex` & `Space`**: Use these for simple linear layouts, button rows, and horizontal/vertical spacing instead of manual flexbox margins.
- **`Row` & `Col`**: Use these for grid layouts (24-column layout system) with responsive breakpoints (`xs`, `sm`, `md`, `lg`, `xl`, `xxl`).
- **`Layout`**: Use for standard page structures consisting of `Header`, `Sider`, `Content`, and `Footer`.

---

## React JSON Schema Form (RJSF) Integration

To dynamically generate structured, reliable forms from JSON Schemas, the project integrates **`react-jsonschema-form` (RJSF)** styled using **Ant Design**.

### 1. Installed Packages

- `@rjsf/core`: The core form engine.
- `@rjsf/antd`: The official Ant Design theme adapter (maps JSON schema fields to `antd` inputs, selects, switches, etc.).
- `@rjsf/utils`: General types and utility functions.
- `@rjsf/validator-ajv8`: Required AJV v8-based validator.

### 2. Standard Usage Example

To render a form styled with Ant Design, import `Form` directly from `@rjsf/antd` and pass the `validator`:

```tsx
import React from 'react';
import Form from '@rjsf/antd';
import validator from '@rjsf/validator-ajv8';
import { RJSFSchema, UiSchema } from '@rjsf/utils';
import { App } from 'antd';

// Define the JSON Schema structure
const schema: RJSFSchema = {
  title: 'Register Scheduled Job',
  description: 'Provide details to schedule a recurring task.',
  type: 'object',
  required: ['name', 'cronExpression'],
  properties: {
    name: {
      type: 'string',
      title: 'Job Name',
      minLength: 3,
    },
    cronExpression: {
      type: 'string',
      title: 'Cron Expression',
      default: '*/5 * * * *',
    },
    enabled: {
      type: 'boolean',
      title: 'Enabled',
      default: true,
    },
    maxRetries: {
      type: 'integer',
      title: 'Max Retries',
      minimum: 0,
      maximum: 10,
      default: 3,
    },
  },
};

// Customize UI layout or specific widgets/placeholders
const uiSchema: UiSchema = {
  cronExpression: {
    'ui:placeholder': 'e.g., 0 0 * * * (every day at midnight)',
  },
  maxRetries: {
    'ui:widget': 'updown', // Renders standard Ant Design InputNumber
  },
};

export const JobCreateForm: React.FC = () => {
  const { message } = App.useApp();

  const handleSubmit = ({ formData }: { formData: any }) => {
    console.log('Submitting schema form data:', formData);
    message.success('Schema form data submitted successfully!');
  };

  return (
    <Form
      schema={schema}
      uiSchema={uiSchema}
      validator={validator}
      onSubmit={handleSubmit}
      showErrorList="top"
      focusOnFirstError
    />
  );
};
```

### 3. Key Benefits of the `@rjsf/antd` Integration

*   **Seamless Global Branding**: Because the form imports elements dynamically from the themed `antd` package, it automatically inherits theme variables (e.g. `colorPrimary`, `borderRadius`) set by the parent `<ConfigProvider>`.
*   **Automatic Ant Design Components**:
    *   Booleans render as `antd` `Switch` or `Checkbox`.
    *   Numbers/Integers automatically render as `antd` `InputNumber`.
    *   Arrays render as dynamic list controllers with add/delete button wrappers.
    *   Validation states integrate directly with standard Ant Design validation borders.

---

## Project Settings

- **Path Aliases**: The `@` symbol points to the `src/` directory. 
  - Configured in: `vite.config.ts`, `tsconfig.app.json`