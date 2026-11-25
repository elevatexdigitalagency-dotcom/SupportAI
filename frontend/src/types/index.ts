export type User = {
  id: number;
  email: string;
  full_name: string;
  role: "user" | "admin";
  email_verified: boolean;
  created_at?: string;
};

export type Workspace = {
  id: number;
  name: string;
  slug: string;
  owner_user_id: number;
  role: "owner" | "admin" | "member";
  created_at?: string;
};

export type AuthSession = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  workspaces: Workspace[];
};

export type Conversation = {
  id: number;
  title: string;
  mode: "personal" | "support";
  customer_id?: string | null;
  status?: "open" | "archived";
  workspace_id?: number | null;
  chatbot_id?: number | null;
  assigned_to_user_id?: number | null;
  created_at: string;
  updated_at: string;
};

export type SourceCitation = {
  source_id: number;
  title: string;
  source_type: string;
  source_uri?: string | null;
  distance?: number | null;
};

export type Message = {
  id?: number;
  conversation_id?: number;
  role: "user" | "assistant";
  content: string;
  sources_json?: string | null;
  sources?: SourceCitation[];
  created_at?: string;
};

export type KnowledgeBase = {
  id: number;
  workspace_id: number;
  name: string;
  description?: string | null;
  collection_name: string;
  source_count?: number;
  created_at: string;
};

export type KnowledgeSource = {
  id: number;
  workspace_id: number;
  knowledge_base_id: number;
  source_type: string;
  title: string;
  source_uri?: string | null;
  file_size_bytes: number;
  chunk_count: number;
  status: "pending" | "processing" | "indexed" | "failed";
  error_message?: string | null;
  created_at: string;
};

export type Chatbot = {
  id: number;
  workspace_id: number;
  public_id: string;
  name: string;
  knowledge_base_id?: number | null;
  knowledge_base_name?: string | null;
  is_enabled: number | boolean;
  allowed_domains: string;
  primary_color: string;
  logo_url?: string | null;
  welcome_message: string;
  system_instructions: string;
  fallback_message: string;
  created_at: string;
};

export type Plan = {
  id: number;
  code: string;
  name: string;
  monthly_price_cents: number;
  monthly_message_limit: number;
  document_limit: number;
  chatbot_limit: number;
  features: string[];
};

export type SubscriptionInfo = {
  subscription: {
    id: number;
    status: string;
    current_period_start: string;
    current_period_end: string;
    plan_code: string;
    plan_name: string;
    monthly_price_cents: number;
    monthly_message_limit: number;
    document_limit: number;
    chatbot_limit: number;
    features: string[];
  };
  usage: {
    period_month: string;
    messages_used: number;
    documents_used: number;
    chatbots_used: number;
  };
  payment_provider_connected: boolean;
};

export type AnalyticsOverview = {
  days: number;
  metrics: {
    total_conversations: number;
    total_messages: number;
    active_chatbots: number;
    knowledge_sources: number;
    monthly_ai_usage: number;
  };
  daily_conversations: { day: string; count: number }[];
  daily_messages: { day: string; count: number }[];
  mode_breakdown: { mode: string; count: number }[];
};
