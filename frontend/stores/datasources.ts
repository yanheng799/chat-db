import { create } from "zustand";
import { api } from "@/lib/api";

export interface DataSource {
  id: string;
  name: string;
  engine: string;
  host: string;
  port: number;
  username: string;
  database: string;
  schema_whitelist: Record<string, string>[] | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DataSourceDetail {
  table_count: number;
  column_count: number;
}

export interface SyncLog {
  id: string;
  data_source_id: string;
  sync_type: string;
  scope: Record<string, unknown>[] | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  tables_added: number | null;
  tables_removed: number | null;
  columns_changed: number | null;
  error_message: string | null;
}

export interface LearningLog {
  id: string;
  data_source_id: string;
  trigger_type: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  tables_processed: number | null;
  columns_described: number | null;
  l0_count: number | null;
  l1_count: number | null;
  l2_count: number | null;
  l2_llm_calls: number | null;
  error_message: string | null;
}

interface DataSourceState {
  dataSources: DataSource[];
  loading: boolean;
  error: string | null;

  loadDataSources: () => Promise<void>;
  createDataSource: (
    data: Record<string, unknown>
  ) => Promise<DataSource>;
  updateDataSource: (
    id: string,
    data: Record<string, unknown>
  ) => Promise<DataSource>;
  deleteDataSource: (id: string) => Promise<void>;
  testConnection: (id: string) => Promise<{
    success: boolean;
    message: string;
  }>;
  activate: (id: string) => Promise<DataSource>;
  deactivate: (id: string) => Promise<DataSource>;
  syncMetadata: (id: string) => Promise<{ sync_log_id: string; message: string }>;
  learnMetadata: (id: string) => Promise<{ message: string }>;
  refreshKnowledge: (id: string) => Promise<{ message: string }>;
  getMetadata: (id: string) => Promise<DataSourceDetail>;
  getSyncLogs: (id: string) => Promise<SyncLog[]>;
  getLearningLogs: (id: string) => Promise<LearningLog[]>;
  getDataSource: (id: string) => Promise<DataSource>;
}

export const useDataSourceStore = create<DataSourceState>((set, get) => ({
  dataSources: [],
  loading: false,
  error: null,

  loadDataSources: async () => {
    set({ loading: true, error: null });
    try {
      const ds = await api.get<DataSource[]>("/api/datasources");
      set({ dataSources: ds, loading: false });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  createDataSource: async (data) => {
    const ds = await api.post<DataSource>("/api/datasources", data);
    set((s) => ({ dataSources: [...s.dataSources, ds] }));
    return ds;
  },

  updateDataSource: async (id, data) => {
    const ds = await api.put<DataSource>(`/api/datasources/${id}`, data);
    set((s) => ({
      dataSources: s.dataSources.map((d) => (d.id === id ? ds : d)),
    }));
    return ds;
  },

  deleteDataSource: async (id) => {
    await api.delete(`/api/datasources/${id}`);
    set((s) => ({ dataSources: s.dataSources.filter((d) => d.id !== id) }));
  },

  testConnection: async (id) => {
    return api.post<{ success: boolean; message: string }>(
      `/api/datasources/${id}/test`
    );
  },

  activate: async (id) => {
    const ds = await api.post<DataSource>(`/api/datasources/${id}/activate`);
    await get().loadDataSources();
    return ds;
  },

  deactivate: async (id) => {
    const ds = await api.post<DataSource>(
      `/api/datasources/${id}/deactivate`
    );
    await get().loadDataSources();
    return ds;
  },

  syncMetadata: async (id) => {
    return api.post<{ sync_log_id: string; message: string }>(
      `/api/datasources/${id}/sync`
    );
  },

  learnMetadata: async (id) => {
    return api.post<{ message: string }>(
      `/api/datasources/${id}/learn`
    );
  },

  refreshKnowledge: async (id) => {
    return api.post<{ message: string }>(
      `/api/datasources/${id}/refresh-knowledge`
    );
  },

  getMetadata: async (id) => {
    return api.get<DataSourceDetail>(`/api/datasources/${id}/metadata`);
  },

  getSyncLogs: async (id) => {
    return api.get<SyncLog[]>(`/api/datasources/${id}/sync-logs`);
  },

  getLearningLogs: async (id) => {
    return api.get<LearningLog[]>(`/api/datasources/${id}/learning-logs`);
  },

  getDataSource: async (id) => {
    return api.get<DataSource>(`/api/datasources/${id}`);
  },
}));
