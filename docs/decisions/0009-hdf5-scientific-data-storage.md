# 9. HDF5 Scientific Data Storage Strategy

Date: 2025-01-14

## Status

Accepted

## Context

The ISI Macroscope Control System must manage large scientific datasets with specific requirements:

- **Stimulus Datasets**: Multi-gigabyte visual pattern arrays with precise parameter metadata
- **Acquisition Data**: Real-time camera streams and synchronized hardware status
- **Analysis Results**: Processed retinotopic maps and derived scientific measurements
- **Dataset Reuse**: Exact parameter matching for stimulus dataset sharing across experiments
- **Cross-Platform Compatibility**: Files must work identically on macOS development and Windows production
- **Scientific Reproducibility**: Complete parameter provenance and validation metadata

Traditional file formats (JSON, NPY, MAT) would either:
1. Lack hierarchical metadata organization capabilities
2. Miss cross-platform binary compatibility guarantees
3. Provide insufficient compression for large scientific datasets
4. Lack atomic write operations for data integrity

## Decision

We will use **HDF5 as the primary scientific data storage format** with structured metadata schemas:

### External Package Strategy
- **Proven Libraries**: h5py as the industry-standard Python HDF5 interface, leveraging decades of optimization
- **Validated Compression**: HDF5's built-in GZIP compression algorithms rather than custom compression implementations
- **Standard Metadata**: Use Pydantic V2's established serialization methods for HDF5 attribute storage
- **Atomic Operations**: Leverage HDF5's native atomic write capabilities and proven file system APIs

### Dataset Organization Strategy
- **Hierarchical Structure**: Organized groups for stimuli, acquisitions, and analysis data
- **Metadata Integration**: Parameter information stored as HDF5 attributes alongside array data
- **Standardized Naming**: Consistent dataset and group naming conventions across all data types
- **Version Compatibility**: Schema designed for forward and backward compatibility with existing scientific data formats

### Dataset Reuse Strategy
- **Standard Hashing**: SHA-256 from Python's proven hashlib library for parameter matching
- **Validated Metadata**: Pydantic V2's built-in validation for schema compliance checking
- **File System APIs**: Operating system file discovery using established pathlib and glob libraries
- **Proven Algorithms**: Leverage existing duplicate detection algorithms from scientific computing packages

## Consequences

### Positive

- **Scientific Standard**: HDF5 is the de facto standard for scientific data storage
- **Cross-Platform Reliability**: Identical binary format across macOS and Windows
- **Efficient Storage**: Built-in compression reduces dataset sizes significantly
- **Metadata Integration**: Hierarchical attributes provide structured parameter storage
- **Data Integrity**: Atomic operations prevent corruption during acquisition
- **Performance**: Optimized for large array operations with chunking and caching
- **Dataset Reuse**: Parameter-based exact matching enables efficient stimulus sharing
- **Tool Ecosystem**: Extensive scientific tooling support (HDFView, h5dump, etc.)

### Negative

- **Learning Curve**: Team must understand HDF5 concepts and best practices
- **Dependency Management**: h5py adds complex binary dependency to deployment
- **Debug Complexity**: Binary format requires specialized tools for inspection
- **Version Compatibility**: HDF5 format evolution may require migration strategies
- **Memory Usage**: Large datasets may require careful memory management strategies

### Risks

- **File Corruption**: Power failures during writes could corrupt datasets
- **Schema Evolution**: Metadata schema changes could break compatibility with existing files
- **Performance Bottlenecks**: Large file operations could block real-time acquisition
- **Storage Requirements**: Uncompressed scientific datasets could exhaust disk space

## Alternatives Considered

- **NumPy NPZ Format**: Rejected due to lack of hierarchical metadata and limited compression
- **JSON + Binary Arrays**: Rejected due to complexity and poor compression characteristics
- **MATLAB MAT Files**: Rejected due to proprietary format and licensing concerns
- **SQLite + BLOB Storage**: Rejected due to poor performance for large array operations
- **Custom Binary Format**: Rejected due to development complexity and lack of tool ecosystem

## Related Decisions

- Depends on: ADR-0003 (Thin Client Architecture - scientific data isolation)
- Depends on: ADR-0004 (Modern Technology Stack - h5py, Pydantic V2)
- Depends on: ADR-0007 (Parameter Separation - metadata organization)
- Enables: Future ADRs on data backup, archival strategies, performance optimization

## Notes

HDF5 choice aligns with scientific computing best practices where data integrity, cross-platform compatibility, and metadata preservation are critical.

Implementation requires:
- Structured Pydantic schemas for all metadata types
- Atomic file operations for data safety during acquisition
- Memory-efficient streaming for large dataset operations
- Comprehensive error handling for file system failures
- Clear documentation of dataset schemas for scientific reproducibility

The format ensures long-term data accessibility and supports the collaborative nature of scientific research where datasets are shared across institutions and platforms.