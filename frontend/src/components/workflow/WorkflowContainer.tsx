/**
 * ISI Macroscope Control System - Workflow Container
 *
 * Main workflow container that displays the appropriate workflow stage
 * based on backend state. Follows thin client pattern - no business logic.
 */

import React from 'react';
import { useWorkflowState, useErrors, useCriticalErrors } from '../../stores/backend-mirror';
import { useNavigation, useNavigationActions } from '../../stores/ui-store';
import { SetupDisplay } from './SetupDisplay';
import { GenerationDisplay } from './GenerationDisplay';
import { AcquisitionDisplay } from './AcquisitionDisplay';
import { AnalysisDisplay } from './AnalysisDisplay';
import { ErrorDisplay } from './ErrorDisplay';
import { StartupDisplay } from './StartupDisplay';

// ============================================================================
// WORKFLOW CONTAINER COMPONENT
// ============================================================================

export const WorkflowContainer: React.FC = () => {
  const workflowState = useWorkflowState();
  const errors = useErrors();
  const criticalErrors = useCriticalErrors();
  const navigation = useNavigation();
  const navigationActions = useNavigationActions();

  // Update UI navigation state when workflow state changes
  React.useEffect(() => {
    if (workflowState?.currentState) {
      const viewMap: Record<string, string> = {
        'STARTUP': 'startup',
        'SETUP_READY': 'setup',
        'SETUP': 'setup',
        'GENERATION_READY': 'generation',
        'GENERATION': 'generation',
        'ACQUISITION_READY': 'acquisition',
        'ACQUISITION': 'acquisition',
        'ANALYSIS_READY': 'analysis',
        'ANALYSIS': 'analysis',
        'ERROR': 'error',
        'RECOVERY': 'error',
        'DEGRADED': 'error',
      };

      const targetView = viewMap[workflowState.currentState];
      if (targetView && navigation.currentView !== targetView) {
        navigationActions.setCurrentView(targetView as any);
      }
    }
  }, [workflowState?.currentState, navigation.currentView, navigationActions]);

  // Show critical errors regardless of workflow state
  if (criticalErrors.length > 0) {
    return <ErrorDisplay errors={criticalErrors} />;
  }

  // Render appropriate workflow display
  switch (workflowState?.currentState) {
    case 'STARTUP':
      return <StartupDisplay workflowState={workflowState} />;

    case 'SETUP_READY':
    case 'SETUP':
      return <SetupDisplay workflowState={workflowState} />;

    case 'GENERATION_READY':
    case 'GENERATION':
      return <GenerationDisplay workflowState={workflowState} />;

    case 'ACQUISITION_READY':
    case 'ACQUISITION':
      return <AcquisitionDisplay workflowState={workflowState} />;

    case 'ANALYSIS_READY':
    case 'ANALYSIS':
      return <AnalysisDisplay workflowState={workflowState} />;

    case 'ERROR':
    case 'RECOVERY':
    case 'DEGRADED':
      return <ErrorDisplay errors={errors} />;

    default:
      return (
        <div style={{ padding: 40, textAlign: 'center', color: '#666' }}>
          <div>System initializing...</div>
          <div style={{ fontSize: 12, marginTop: 8 }}>
            Waiting for backend connection
          </div>
        </div>
      );
  }
};

export default WorkflowContainer;