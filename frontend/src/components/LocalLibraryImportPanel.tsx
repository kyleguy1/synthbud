import { useMemo, useState } from "react";
import type { LibraryImportResponse } from "../types";
import { getRuntimeConfig, pickDirectory } from "../lib/runtime";

interface LocalLibraryImportPanelProps {
  title: string;
  description: string;
  roots: string[];
  importLabel: string;
  emptyMessage: string;
  onImport: (path: string) => Promise<LibraryImportResponse>;
  onImported: (response: LibraryImportResponse) => void;
}

function buildImportMessage(response: LibraryImportResponse): string {
  const importResult = response.import_result;
  const ingestedCount = Number(importResult.ingested_count ?? 0);
  const failedCount = Number(importResult.failed_count ?? importResult.parse_failed_count ?? 0);
  const scannedFiles = Number(importResult.scanned_files ?? 0);
  const parts = [
    `${ingestedCount} item${ingestedCount === 1 ? "" : "s"} indexed`,
    scannedFiles > 0 ? `${scannedFiles} file${scannedFiles === 1 ? "" : "s"} scanned` : null,
    failedCount > 0 ? `${failedCount} skipped` : null
  ].filter(Boolean);

  if (parts.length > 0) {
    return `${parts.join(" · ")}.`;
  }

  return response.added ? "Library folder imported." : "Library folder refreshed.";
}

export function LocalLibraryImportPanel(props: LocalLibraryImportPanelProps) {
  const [pathInput, setPathInput] = useState("");
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canPickDirectory = useMemo(() => getRuntimeConfig().capabilities.pickDirectory, []);

  async function handleChooseFolder() {
    const selectedPath = await pickDirectory();
    if (selectedPath) {
      setPathInput(selectedPath);
      setError(null);
    }
  }

  async function handleImport() {
    const normalizedPath = pathInput.trim();
    if (!normalizedPath) {
      setError("Choose or paste a folder path first.");
      return;
    }

    setImporting(true);
    setError(null);
    setMessage(null);
    try {
      const response = await props.onImport(normalizedPath);
      setMessage(buildImportMessage(response));
      setPathInput("");
      props.onImported(response);
    } catch (importError) {
      if (importError instanceof Error) {
        setError(importError.message);
      } else {
        setError("Unable to import this folder right now.");
      }
    } finally {
      setImporting(false);
    }
  }

  return (
    <section className="library-import-panel">
      <div className="library-import-header">
        <div>
          <p className="preset-discovery-eyebrow">Local Import</p>
          <h3>{props.title}</h3>
        </div>
        {canPickDirectory ? (
          <button
            type="button"
            className="preset-secondary-button"
            onClick={() => void handleChooseFolder()}
          >
            Choose folder
          </button>
        ) : null}
      </div>

      <p className="library-import-copy">{props.description}</p>

      <div className="library-import-inputs">
        <input
          type="text"
          aria-label={`${props.title} path`}
          placeholder="/Users/you/Library/Samples"
          value={pathInput}
          onChange={(event) => setPathInput(event.target.value)}
        />
        <button
          type="button"
          className="preset-sync-button library-import-action"
          onClick={() => void handleImport()}
          disabled={importing}
        >
          {importing ? "Importing..." : props.importLabel}
        </button>
      </div>

      {message ? <p className="library-import-message">{message}</p> : null}
      {error ? <p className="error library-import-message">{error}</p> : null}

      <div className="library-import-roots">
        <p className="library-import-roots-label">Tracked folders</p>
        {props.roots.length === 0 ? (
          <p className="library-import-empty">{props.emptyMessage}</p>
        ) : (
          <ul className="library-import-root-list">
            {props.roots.map((root) => (
              <li key={root}>{root}</li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
