import { create } from "zustand";

interface AdminState {
  activeDataSourceId: string | null;
  activeDataSourceName: string | null;

  // per-card loading/error
  syncLoading: boolean;
  syncError: string | null;
  graphLoading: boolean;
  graphError: string | null;
  mappingsLoading: boolean;
  mappingsError: string | null;
  hotwordsLoading: boolean;
  hotwordsError: string | null;
  periodsLoading: boolean;
  periodsError: string | null;
  auditLoading: boolean;
  auditError: string | null;

  setActiveDataSource: (id: string, name: string) => void;
  setSyncLoading: (v: boolean) => void;
  setSyncError: (e: string | null) => void;
  setGraphLoading: (v: boolean) => void;
  setGraphError: (e: string | null) => void;
  setMappingsLoading: (v: boolean) => void;
  setMappingsError: (e: string | null) => void;
  setHotwordsLoading: (v: boolean) => void;
  setHotwordsError: (e: string | null) => void;
  setPeriodsLoading: (v: boolean) => void;
  setPeriodsError: (e: string | null) => void;
  setAuditLoading: (v: boolean) => void;
  setAuditError: (e: string | null) => void;
}

export const useAdminStore = create<AdminState>((set) => ({
  activeDataSourceId: null,
  activeDataSourceName: null,

  syncLoading: false,
  syncError: null,
  graphLoading: false,
  graphError: null,
  mappingsLoading: false,
  mappingsError: null,
  hotwordsLoading: false,
  hotwordsError: null,
  periodsLoading: false,
  periodsError: null,
  auditLoading: false,
  auditError: null,

  setActiveDataSource: (id, name) =>
    set({ activeDataSourceId: id, activeDataSourceName: name }),
  setSyncLoading: (v) => set({ syncLoading: v }),
  setSyncError: (e) => set({ syncError: e }),
  setGraphLoading: (v) => set({ graphLoading: v }),
  setGraphError: (e) => set({ graphError: e }),
  setMappingsLoading: (v) => set({ mappingsLoading: v }),
  setMappingsError: (e) => set({ mappingsError: e }),
  setHotwordsLoading: (v) => set({ hotwordsLoading: v }),
  setHotwordsError: (e) => set({ hotwordsError: e }),
  setPeriodsLoading: (v) => set({ periodsLoading: v }),
  setPeriodsError: (e) => set({ periodsError: e }),
  setAuditLoading: (v) => set({ auditLoading: v }),
  setAuditError: (e) => set({ auditError: e }),
}));
