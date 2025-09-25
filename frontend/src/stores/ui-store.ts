/**
 * ISI Macroscope Control System - UI State Store
 *
 * Pure UI state management using Zustand.
 * Contains ONLY frontend UI state - no business logic or backend state mirroring.
 * All backend state flows through as read-only display data.
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

// ============================================================================
// UI STATE INTERFACE
// ============================================================================

export interface UIState {
  // Modal and dialog state
  modals: {
    isParameterModalOpen: boolean;
    isErrorModalOpen: boolean;
    isConfirmationModalOpen: boolean;
    isHelpModalOpen: boolean;
  };

  // Panel visibility and layout
  panels: {
    isLeftPanelCollapsed: boolean;
    isRightPanelCollapsed: boolean;
    selectedLeftPanel: LeftPanelType;
    selectedRightPanel: RightPanelType;
  };

  // View options and display preferences
  display: {
    theme: 'light' | 'dark' | 'auto';
    zoom: number;
    selectedVisualization: VisualizationType;
    showGrid: boolean;
    showMeasurements: boolean;
    previewQuality: 'low' | 'medium' | 'high';
  };

  // Form state (UI validation only, not business validation)
  forms: {
    hasUnsavedChanges: boolean;
    activeFormElement: string | null;
    formValidationErrors: Record<string, string>;
  };

  // Navigation and routing state
  navigation: {
    currentView: ViewType;
    navigationHistory: ViewType[];
    canGoBack: boolean;
    breadcrumbs: Breadcrumb[];
  };

  // Loading and interaction state
  interaction: {
    isLoading: boolean;
    loadingMessage: string;
    hoveredElement: string | null;
    focusedElement: string | null;
    dragState: DragState | null;
  };

  // Error and notification state (UI display only)
  notifications: {
    toasts: Toast[];
    activeNotificationId: string | null;
    isNotificationsPanelOpen: boolean;
  };

  // Performance and debug state
  debug: {
    showFPS: boolean;
    showMemoryUsage: boolean;
    showNetworkStats: boolean;
    enableDebugMode: boolean;
  };
}

// ============================================================================
// UI STATE TYPES
// ============================================================================

export type LeftPanelType =
  | 'parameters'
  | 'hardware-status'
  | 'session-info'
  | 'help';

export type RightPanelType =
  | 'preview'
  | 'progress'
  | 'logs'
  | 'diagnostics';

export type VisualizationType =
  | '2d-parameters'
  | '3d-spatial'
  | 'live-preview'
  | 'results-maps';

export type ViewType =
  | 'startup'
  | 'setup'
  | 'generation'
  | 'acquisition'
  | 'analysis'
  | 'error'
  | 'settings';

export interface Breadcrumb {
  readonly label: string;
  readonly view: ViewType;
  readonly isEnabled: boolean;
}

export interface DragState {
  readonly elementId: string;
  readonly startPosition: { x: number; y: number };
  readonly currentPosition: { x: number; y: number };
  readonly isDragging: boolean;
}

export interface Toast {
  readonly id: string;
  readonly type: 'info' | 'success' | 'warning' | 'error';
  readonly title: string;
  readonly message: string;
  readonly isVisible: boolean;
  readonly autoDismiss: boolean;
  readonly dismissAfterMs?: number;
}

// ============================================================================
// UI ACTIONS INTERFACE
// ============================================================================

export interface UIActions {
  // Modal actions
  openModal: (modalType: keyof UIState['modals']) => void;
  closeModal: (modalType: keyof UIState['modals']) => void;
  closeAllModals: () => void;

  // Panel actions
  toggleLeftPanel: () => void;
  toggleRightPanel: () => void;
  selectLeftPanel: (panel: LeftPanelType) => void;
  selectRightPanel: (panel: RightPanelType) => void;

  // Display actions
  setTheme: (theme: UIState['display']['theme']) => void;
  setZoom: (zoom: number) => void;
  setVisualization: (type: VisualizationType) => void;
  toggleGrid: () => void;
  toggleMeasurements: () => void;
  setPreviewQuality: (quality: UIState['display']['previewQuality']) => void;

  // Form actions (UI state only)
  setUnsavedChanges: (hasChanges: boolean) => void;
  setActiveFormElement: (element: string | null) => void;
  setFormValidationError: (field: string, error: string) => void;
  clearFormValidationErrors: () => void;

  // Navigation actions
  setCurrentView: (view: ViewType) => void;
  goBack: () => void;
  updateBreadcrumbs: (breadcrumbs: Breadcrumb[]) => void;

  // Interaction actions
  setLoading: (isLoading: boolean, message?: string) => void;
  setHoveredElement: (element: string | null) => void;
  setFocusedElement: (element: string | null) => void;
  setDragState: (state: DragState | null) => void;

  // Notification actions
  addToast: (toast: Omit<Toast, 'id' | 'isVisible'>) => void;
  dismissToast: (id: string) => void;
  clearAllToasts: () => void;
  toggleNotificationsPanel: () => void;

  // Debug actions
  toggleFPS: () => void;
  toggleMemoryUsage: () => void;
  toggleNetworkStats: () => void;
  setDebugMode: (enabled: boolean) => void;

  // Utility actions
  resetUIState: () => void;
  getSnapshot: () => UIState;
}

// ============================================================================
// INITIAL STATE
// ============================================================================

const initialState: UIState = {
  modals: {
    isParameterModalOpen: false,
    isErrorModalOpen: false,
    isConfirmationModalOpen: false,
    isHelpModalOpen: false,
  },

  panels: {
    isLeftPanelCollapsed: false,
    isRightPanelCollapsed: false,
    selectedLeftPanel: 'parameters',
    selectedRightPanel: 'preview',
  },

  display: {
    theme: 'auto',
    zoom: 1.0,
    selectedVisualization: '2d-parameters',
    showGrid: true,
    showMeasurements: true,
    previewQuality: 'medium',
  },

  forms: {
    hasUnsavedChanges: false,
    activeFormElement: null,
    formValidationErrors: {},
  },

  navigation: {
    currentView: 'startup',
    navigationHistory: ['startup'],
    canGoBack: false,
    breadcrumbs: [{ label: 'System Startup', view: 'startup', isEnabled: true }],
  },

  interaction: {
    isLoading: false,
    loadingMessage: '',
    hoveredElement: null,
    focusedElement: null,
    dragState: null,
  },

  notifications: {
    toasts: [],
    activeNotificationId: null,
    isNotificationsPanelOpen: false,
  },

  debug: {
    showFPS: false,
    showMemoryUsage: false,
    showNetworkStats: false,
    enableDebugMode: false,
  },
};

// ============================================================================
// ZUSTAND STORE
// ============================================================================

export const useUIStore = create<UIState & UIActions>()(
  devtools(
    (set, get) => ({
      ...initialState,

      // Modal actions
      openModal: (modalType) =>
        set((state) => ({
          modals: {
            ...state.modals,
            [modalType]: true,
          },
        })),

      closeModal: (modalType) =>
        set((state) => ({
          modals: {
            ...state.modals,
            [modalType]: false,
          },
        })),

      closeAllModals: () =>
        set((state) => ({
          modals: Object.keys(state.modals).reduce(
            (acc, key) => ({ ...acc, [key]: false }),
            {} as UIState['modals']
          ),
        })),

      // Panel actions
      toggleLeftPanel: () =>
        set((state) => ({
          panels: {
            ...state.panels,
            isLeftPanelCollapsed: !state.panels.isLeftPanelCollapsed,
          },
        })),

      toggleRightPanel: () =>
        set((state) => ({
          panels: {
            ...state.panels,
            isRightPanelCollapsed: !state.panels.isRightPanelCollapsed,
          },
        })),

      selectLeftPanel: (panel) =>
        set((state) => ({
          panels: {
            ...state.panels,
            selectedLeftPanel: panel,
            isLeftPanelCollapsed: false, // Auto-expand when selecting
          },
        })),

      selectRightPanel: (panel) =>
        set((state) => ({
          panels: {
            ...state.panels,
            selectedRightPanel: panel,
            isRightPanelCollapsed: false, // Auto-expand when selecting
          },
        })),

      // Display actions
      setTheme: (theme) =>
        set((state) => ({
          display: { ...state.display, theme },
        })),

      setZoom: (zoom) =>
        set((state) => ({
          display: { ...state.display, zoom: Math.max(0.5, Math.min(3.0, zoom)) },
        })),

      setVisualization: (type) =>
        set((state) => ({
          display: { ...state.display, selectedVisualization: type },
        })),

      toggleGrid: () =>
        set((state) => ({
          display: { ...state.display, showGrid: !state.display.showGrid },
        })),

      toggleMeasurements: () =>
        set((state) => ({
          display: { ...state.display, showMeasurements: !state.display.showMeasurements },
        })),

      setPreviewQuality: (quality) =>
        set((state) => ({
          display: { ...state.display, previewQuality: quality },
        })),

      // Form actions
      setUnsavedChanges: (hasChanges) =>
        set((state) => ({
          forms: { ...state.forms, hasUnsavedChanges: hasChanges },
        })),

      setActiveFormElement: (element) =>
        set((state) => ({
          forms: { ...state.forms, activeFormElement: element },
        })),

      setFormValidationError: (field, error) =>
        set((state) => ({
          forms: {
            ...state.forms,
            formValidationErrors: {
              ...state.forms.formValidationErrors,
              [field]: error,
            },
          },
        })),

      clearFormValidationErrors: () =>
        set((state) => ({
          forms: { ...state.forms, formValidationErrors: {} },
        })),

      // Navigation actions
      setCurrentView: (view) => {
        const state = get();
        const history = [...state.navigation.navigationHistory, view];

        set({
          navigation: {
            ...state.navigation,
            currentView: view,
            navigationHistory: history,
            canGoBack: history.length > 1,
          },
        });
      },

      goBack: () => {
        const state = get();
        if (state.navigation.canGoBack) {
          const history = state.navigation.navigationHistory;
          const newHistory = history.slice(0, -1);
          const previousView = newHistory[newHistory.length - 1];

          set({
            navigation: {
              ...state.navigation,
              currentView: previousView,
              navigationHistory: newHistory,
              canGoBack: newHistory.length > 1,
            },
          });
        }
      },

      updateBreadcrumbs: (breadcrumbs) =>
        set((state) => ({
          navigation: { ...state.navigation, breadcrumbs },
        })),

      // Interaction actions
      setLoading: (isLoading, message = '') =>
        set((state) => ({
          interaction: {
            ...state.interaction,
            isLoading,
            loadingMessage: message,
          },
        })),

      setHoveredElement: (element) =>
        set((state) => ({
          interaction: { ...state.interaction, hoveredElement: element },
        })),

      setFocusedElement: (element) =>
        set((state) => ({
          interaction: { ...state.interaction, focusedElement: element },
        })),

      setDragState: (dragState) =>
        set((state) => ({
          interaction: { ...state.interaction, dragState },
        })),

      // Notification actions
      addToast: (toastData) => {
        const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const toast: Toast = {
          ...toastData,
          id,
          isVisible: true,
        };

        set((state) => ({
          notifications: {
            ...state.notifications,
            toasts: [...state.notifications.toasts, toast],
            activeNotificationId: id,
          },
        }));

        // Auto-dismiss if specified
        if (toast.autoDismiss && toast.dismissAfterMs) {
          setTimeout(() => {
            get().dismissToast(id);
          }, toast.dismissAfterMs);
        }
      },

      dismissToast: (id) =>
        set((state) => ({
          notifications: {
            ...state.notifications,
            toasts: state.notifications.toasts.filter((toast) => toast.id !== id),
            activeNotificationId: state.notifications.activeNotificationId === id
              ? null
              : state.notifications.activeNotificationId,
          },
        })),

      clearAllToasts: () =>
        set((state) => ({
          notifications: {
            ...state.notifications,
            toasts: [],
            activeNotificationId: null,
          },
        })),

      toggleNotificationsPanel: () =>
        set((state) => ({
          notifications: {
            ...state.notifications,
            isNotificationsPanelOpen: !state.notifications.isNotificationsPanelOpen,
          },
        })),

      // Debug actions
      toggleFPS: () =>
        set((state) => ({
          debug: { ...state.debug, showFPS: !state.debug.showFPS },
        })),

      toggleMemoryUsage: () =>
        set((state) => ({
          debug: { ...state.debug, showMemoryUsage: !state.debug.showMemoryUsage },
        })),

      toggleNetworkStats: () =>
        set((state) => ({
          debug: { ...state.debug, showNetworkStats: !state.debug.showNetworkStats },
        })),

      setDebugMode: (enabled) =>
        set((state) => ({
          debug: { ...state.debug, enableDebugMode: enabled },
        })),

      // Utility actions
      resetUIState: () => set(initialState),

      getSnapshot: () => get(),
    }),
    {
      name: 'ui-store',
      enabled: process.env.NODE_ENV === 'development',
    }
  )
);

// ============================================================================
// SELECTOR HOOKS FOR PERFORMANCE
// ============================================================================

// Modal selectors
export const useModals = () => useUIStore((state) => state.modals);
export const useModalActions = () => useUIStore((state) => ({
  openModal: state.openModal,
  closeModal: state.closeModal,
  closeAllModals: state.closeAllModals,
}));

// Panel selectors
export const usePanels = () => useUIStore((state) => state.panels);
export const usePanelActions = () => useUIStore((state) => ({
  toggleLeftPanel: state.toggleLeftPanel,
  toggleRightPanel: state.toggleRightPanel,
  selectLeftPanel: state.selectLeftPanel,
  selectRightPanel: state.selectRightPanel,
}));

// Display selectors
export const useDisplay = () => useUIStore((state) => state.display);
export const useDisplayActions = () => useUIStore((state) => ({
  setTheme: state.setTheme,
  setZoom: state.setZoom,
  setVisualization: state.setVisualization,
  toggleGrid: state.toggleGrid,
  toggleMeasurements: state.toggleMeasurements,
  setPreviewQuality: state.setPreviewQuality,
}));

// Navigation selectors
export const useNavigation = () => useUIStore((state) => state.navigation);
export const useNavigationActions = () => useUIStore((state) => ({
  setCurrentView: state.setCurrentView,
  goBack: state.goBack,
  updateBreadcrumbs: state.updateBreadcrumbs,
}));

// Interaction selectors
export const useInteraction = () => useUIStore((state) => state.interaction);
export const useInteractionActions = () => useUIStore((state) => ({
  setLoading: state.setLoading,
  setHoveredElement: state.setHoveredElement,
  setFocusedElement: state.setFocusedElement,
  setDragState: state.setDragState,
}));

// Notification selectors
export const useNotifications = () => useUIStore((state) => state.notifications);
export const useNotificationActions = () => useUIStore((state) => ({
  addToast: state.addToast,
  dismissToast: state.dismissToast,
  clearAllToasts: state.clearAllToasts,
  toggleNotificationsPanel: state.toggleNotificationsPanel,
}));