/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import { X } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import type { TAuthorityType, TKnowledgeSource, TSensitivity, TSourceType } from "./knowledge-types";

type TKnowledgeSourceFormProps = {
  source?: TKnowledgeSource;
  onSubmit: (data: Partial<TKnowledgeSource>) => Promise<void>;
  onCancel: () => void;
  isSubmitting?: boolean;
};

const SOURCE_TYPES: TSourceType[] = ["plane", "repository", "ci", "incident", "external"];
const AUTHORITY_TYPES: TAuthorityType[] = [
  "product", "design", "architecture", "qa", "security", "platform", "release",
];
const SENSITIVITY_LEVELS: TSensitivity[] = ["public", "internal", "confidential", "restricted"];

export function KnowledgeSourceForm(props: TKnowledgeSourceFormProps) {
  const { source, onSubmit, onCancel, isSubmitting = false } = props;
  const { t } = useTranslation();
  const isEditing = Boolean(source);

  const [formData, setFormData] = useState({
    name: source?.name ?? "",
    source_type: source?.source_type ?? ("external" as TSourceType),
    authority_type: source?.authority_type ?? ("product" as TAuthorityType),
    sensitivity: source?.sensitivity ?? ("internal" as TSensitivity),
    url: source?.url ?? "",
    owner: source?.owner ?? "",
    effective_from: source?.effective_from?.slice(0, 10) ?? "",
    expires_at: source?.expires_at?.slice(0, 10) ?? "",
    retention_days: source?.retention_days ?? 365,
  });

  const handleChange = useCallback(
    (field: string, value: string | number) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
    },
    []
  );

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      await onSubmit({
        ...formData,
        effective_from: formData.effective_from || null,
        expires_at: formData.expires_at || null,
        owner: formData.owner || null,
      } as Partial<TKnowledgeSource>);
    },
    [formData, onSubmit]
  );

  return (
    <div className="rounded-lg border border-subtle bg-surface-1 p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-16 font-semibold text-primary">
          {isEditing ? "Edit Knowledge Source" : "Register Knowledge Source"}
        </h3>
        <button type="button" onClick={onCancel} className="text-tertiary hover:text-primary" aria-label="Close form">
          <X className="h-4 w-4" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1">
            <label htmlFor="ks-name" className="text-12 font-medium text-secondary">Name *</label>
            <input
              id="ks-name"
              type="text"
              required
              value={formData.name}
              onChange={(e) => handleChange("name", e.target.value)}
              className="rounded-md border border-subtle bg-surface-2 px-3 py-2 text-13 text-primary placeholder:text-quaternary focus:border-accent-primary focus:outline-none"
              placeholder="e.g., API Design Specification"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="ks-url" className="text-12 font-medium text-secondary">URL</label>
            <input
              id="ks-url"
              type="url"
              value={formData.url}
              onChange={(e) => handleChange("url", e.target.value)}
              className="rounded-md border border-subtle bg-surface-2 px-3 py-2 text-13 text-primary placeholder:text-quaternary focus:border-accent-primary focus:outline-none"
              placeholder="https://..."
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="ks-source-type" className="text-12 font-medium text-secondary">Source Type *</label>
            <select
              id="ks-source-type"
              value={formData.source_type}
              onChange={(e) => handleChange("source_type", e.target.value)}
              className="rounded-md border border-subtle bg-surface-2 px-3 py-2 text-13 text-primary focus:border-accent-primary focus:outline-none"
            >
              {SOURCE_TYPES.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="ks-authority-type" className="text-12 font-medium text-secondary">
              {t("agent_infra.knowledge.authority")} *
            </label>
            <select
              id="ks-authority-type"
              value={formData.authority_type}
              onChange={(e) => handleChange("authority_type", e.target.value)}
              className="rounded-md border border-subtle bg-surface-2 px-3 py-2 text-13 text-primary focus:border-accent-primary focus:outline-none"
            >
              {AUTHORITY_TYPES.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="ks-sensitivity" className="text-12 font-medium text-secondary">
              {t("agent_infra.knowledge.sensitivity")} *
            </label>
            <select
              id="ks-sensitivity"
              value={formData.sensitivity}
              onChange={(e) => handleChange("sensitivity", e.target.value)}
              className="rounded-md border border-subtle bg-surface-2 px-3 py-2 text-13 text-primary focus:border-accent-primary focus:outline-none"
            >
              {SENSITIVITY_LEVELS.map((level) => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="ks-owner" className="text-12 font-medium text-secondary">Owner</label>
            <input
              id="ks-owner"
              type="text"
              value={formData.owner}
              onChange={(e) => handleChange("owner", e.target.value)}
              className="rounded-md border border-subtle bg-surface-2 px-3 py-2 text-13 text-primary placeholder:text-quaternary focus:border-accent-primary focus:outline-none"
              placeholder="Team or individual name"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="ks-effective-from" className="text-12 font-medium text-secondary">Effective From</label>
            <input
              id="ks-effective-from"
              type="date"
              value={formData.effective_from}
              onChange={(e) => handleChange("effective_from", e.target.value)}
              className="rounded-md border border-subtle bg-surface-2 px-3 py-2 text-13 text-primary focus:border-accent-primary focus:outline-none"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="ks-expires-at" className="text-12 font-medium text-secondary">Expires At</label>
            <input
              id="ks-expires-at"
              type="date"
              value={formData.expires_at}
              onChange={(e) => handleChange("expires_at", e.target.value)}
              className="rounded-md border border-subtle bg-surface-2 px-3 py-2 text-13 text-primary focus:border-accent-primary focus:outline-none"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="ks-retention" className="text-12 font-medium text-secondary">Retention (days)</label>
            <input
              id="ks-retention"
              type="number"
              min={1}
              value={formData.retention_days}
              onChange={(e) => handleChange("retention_days", parseInt(e.target.value) || 365)}
              className="rounded-md border border-subtle bg-surface-2 px-3 py-2 text-13 text-primary focus:border-accent-primary focus:outline-none"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          <Button variant="neutral-primary" size="sm" onClick={onCancel} type="button">
            Cancel
          </Button>
          <Button variant="primary" size="sm" type="submit" disabled={isSubmitting || !formData.name}>
            {isSubmitting ? "Saving..." : isEditing ? "Update Source" : "Register Source"}
          </Button>
        </div>
      </form>
    </div>
  );
}
