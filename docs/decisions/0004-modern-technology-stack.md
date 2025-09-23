# 4. Modern Technology Stack for 2025

Date: 2025-01-14

## Status

Accepted

## Context

The ISI Macroscope Control System requires a modern, maintainable technology stack that supports:

- Cross-platform desktop development (macOS development, Windows production)
- Scientific computing with GPU acceleration (CUDA, DirectX 12)
- Real-time data processing and visualization
- Type safety and developer productivity
- Long-term maintainability and community support
- Hardware integration with C++ libraries (PCO SDK, DirectX)

Legacy technology choices would limit our ability to leverage modern tooling, GPU acceleration, and development best practices while increasing maintenance burden.

## Decision

We will adopt a **modern 2025 technology stack** with validated, industry-standard tools:

### Frontend Stack
- **Electron 32+**: Cross-platform desktop framework (Node 22 support)
- **React 18/19**: Component-based UI framework
- **TypeScript**: Type safety and enhanced developer experience
- **Vite**: Modern build tool and development server
- **Tailwind CSS**: Utility-first styling framework
- **Zustand 5.0.8**: Lightweight state management with TypeScript support
- **React Three Fiber 9.3.0**: 3D visualization for spatial configuration (WebGPU support)
- **Chart.js + react-chartjs-2**: Scientific data visualization
- **Vitest**: Testing framework (Vite-integrated)

### Backend Stack
- **Python 3.11+**: Core runtime with asyncio for concurrent operations
- **Poetry**: Modern dependency management and packaging
- **Pydantic V2**: Data validation, settings management, and IPC message validation
- **h5py**: HDF5 file handling for scientific datasets
- **CuPy 13.6.0**: CUDA acceleration (supports CUDA 11.x-13.x, NumPy 1.22-2.3)
- **pybind11 2.13.6+**: C++ bindings for DirectX and PCO SDK integration
- **NumPy/SciPy**: Scientific computing foundation
- **OpenCV + Pillow**: Image processing and computer vision
- **pytest**: Comprehensive testing framework

### Development Tools
- **ESLint + Prettier**: Frontend code quality and formatting
- **black + ruff**: Python code formatting and linting
- **GitHub Actions**: Cross-platform CI/CD automation

## Consequences

### Positive

- **Modern Best Practices**: All tools represent current industry standards with active development
- **Type Safety**: TypeScript and Pydantic V2 provide comprehensive type validation
- **Developer Experience**: Modern tooling improves productivity and reduces errors
- **Performance**: Native GPU acceleration through CuPy and DirectX integration
- **Maintainability**: Well-supported libraries with large communities and documentation
- **Testing**: Comprehensive testing frameworks for both frontend and backend
- **Cross-Platform**: Consistent development experience across macOS and Windows

### Negative

- **Learning Curve**: Team must familiarize with modern tools if using legacy technologies
- **Dependency Management**: More complex dependency trees than simpler stacks
- **Version Updates**: Must stay current with rapidly evolving JavaScript/Python ecosystems
- **Build Complexity**: Modern build tools require more configuration than simple scripts

### Risks

- **Version Compatibility**: Mismatched versions between interdependent packages
- **Breaking Changes**: Major version updates could require significant refactoring
- **Ecosystem Stability**: Newer packages may have undiscovered issues

## Alternatives Considered

- **Legacy Electron/JavaScript**: Rejected due to lack of type safety and modern tooling
- **Native C++ Application**: Rejected due to development complexity and cross-platform challenges
- **Python 3.8/older tools**: Rejected due to missing modern features and performance improvements
- **Alternative UI Frameworks (Qt/Tkinter)**: Rejected due to web technology advantages for scientific visualization
- **Alternative State Management (Redux)**: Rejected in favor of simpler, more modern Zustand

## Related Decisions

- Builds on: ADR-0003 (Thin Client Architecture)
- Enables: Future ADRs on build system, testing strategy, deployment

## Notes

Technology choices were validated through research of latest stable versions as of January 2025. All selected tools have:
- Active maintenance and large communities
- Proven track record in production environments
- Excellent TypeScript/Python integration
- Strong performance characteristics for scientific computing

The stack prioritizes type safety, modern development practices, and scientific computing capabilities while maintaining cross-platform compatibility.