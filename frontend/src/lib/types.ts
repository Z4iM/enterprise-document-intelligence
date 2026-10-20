export type StructuredData = Record<string, unknown> | null;

export interface DocumentSummary {
  document_id: string;
  filename: string;
  document_type: string | null;
  classification_confidence: number | null;
  structured_extraction_method: string | null;
  review_status: string;
  processing_status: string;
  created_at: string;
}

export interface DocumentDetail extends DocumentSummary {
  content_type: string | null;
  detected_type: string | null;
  extraction_method: string | null;
  structured_data: StructuredData;
  file_size_bytes: number;
  file_hash: string;
  text_length: number;
  text_preview: string;
  updated_at: string;
}

export interface UploadResponse extends Omit<DocumentDetail, "created_at" | "updated_at"> {}

export interface PendingReview {
  document_id: string;
  filename: string;
  document_type: string | null;
  classification_confidence: number | null;
  structured_extraction_method: string | null;
  structured_data: StructuredData;
  created_at: string;
}

export interface ReviewEvent {
  id: number;
  decision: string;
  reviewer: string | null;
  before_data: StructuredData;
  corrections: StructuredData;
  after_data: StructuredData;
  notes: string | null;
  created_at: string;
}

export interface AuditEvent {
  id: number;
  event_type: string;
  message: string | null;
  created_at: string;
}

export interface ValidationRuleResult {
  rule_id: string;
  applicable: boolean;
  triggered: boolean | null;
  status: string;
  explanation: string;
}

export interface ValidationResult {
  validation_id: number;
  document_id: string;
  policy_id: string;
  status: string;
  validation: {
    engine: string;
    summary: string;
    rules_evaluated: number;
    applicable_rules: number;
    required_actions: string[];
    rule_results: ValidationRuleResult[];
    evidence: Evidence[];
  };
  evidence: Evidence[];
}

export interface Evidence {
  policy_id: string;
  rule_id: string;
  chunk_id: string;
  source_quote: string;
}

export interface PolicyUploadResponse {
  policy_id: string;
  filename: string;
  extraction_method: string;
  text_length: number;
  chunks_created: number;
}

export interface StoredRule {
  id: string;
  rule_id: string;
  rule_data: {
    category: string;
    field: string;
    operator: string;
    threshold: string;
    currency: string;
    action: string;
    approval_role: string | null;
    source_quote: string;
  };
  verification_status: string;
  approval_status: string;
  approved_by: string | null;
}

export interface PolicyRulesResponse {
  policy_id: string;
  total_rules: number;
  rules: StoredRule[];
}

export interface KnownPolicy { policy_id: string; filename: string; added_at: string; }
