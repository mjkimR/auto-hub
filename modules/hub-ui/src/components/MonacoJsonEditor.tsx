import React, { useCallback, useRef } from 'react';
import Editor, { type OnMount } from '@monaco-editor/react';
import { Skeleton } from 'antd';
import { useThemeStore } from '../stores/themeStore';

interface MonacoJsonEditorProps {
  value?: string;
  onChange?: (value: string) => void;
  height?: number | string;
  readOnly?: boolean;
}

/**
 * A reusable Monaco editor wrapper for JSON editing.
 * Integrates with antd Form via value/onChange props (compatible with Form.Item).
 * Automatically syncs with the app's dark/light mode from useThemeStore.
 */
export const MonacoJsonEditor: React.FC<MonacoJsonEditorProps> = ({
  value,
  onChange,
  height = 300,
  readOnly = false,
}) => {
  const { isDarkMode } = useThemeStore();
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);

  const handleMount: OnMount = useCallback((editor) => {
    editorRef.current = editor;
    // Auto-format JSON on mount for a clean initial presentation
    editor.getAction('editor.action.formatDocument')?.run();
  }, []);

  const handleChange = useCallback(
    (newValue: string | undefined) => {
      onChange?.(newValue ?? '');
    },
    [onChange]
  );

  return (
    <div
      style={{
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        overflow: 'hidden',
        // Ensure the editor container participates in antd Form validation styling
        transition: 'border-color 0.2s',
      }}
    >
      <Editor
        height={height}
        language="json"
        theme={isDarkMode ? 'vs-dark' : 'light'}
        value={value}
        onChange={handleChange}
        onMount={handleMount}
        loading={
          <Skeleton.Input
            active
            block
            style={{ height: typeof height === 'number' ? height : 300 }}
          />
        }
        options={{
          readOnly,
          minimap: { enabled: false },
          lineNumbers: 'off',
          glyphMargin: false,
          folding: false,
          lineDecorationsWidth: 0,
          lineNumbersMinChars: 0,
          scrollBeyondLastLine: false,
          wordWrap: 'on',
          formatOnPaste: true,
          formatOnType: true,
          tabSize: 2,
          fontSize: 13,
          fontFamily: '"Fira Code", "JetBrains Mono", "Cascadia Code", Menlo, Consolas, monospace',
          padding: { top: 12, bottom: 12 },
          scrollbar: {
            verticalScrollbarSize: 6,
            horizontalScrollbarSize: 6,
          },
          bracketPairColorization: { enabled: true },
          renderLineHighlight: 'line',
          overviewRulerLanes: 0,
        }}
      />
    </div>
  );
};
