import React from 'react';

const SIZES = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-10 w-10 border-[3px]',
};

export const Spinner: React.FC<{ size?: keyof typeof SIZES; className?: string }> = ({ size = 'md', className = '' }) => (
  <div
    role="status"
    aria-label="Loading"
    className={`inline-block animate-spin rounded-full border-slate-300 border-t-brand-500 dark:border-slate-700 dark:border-t-brand-400 ${SIZES[size]} ${className}`}
  />
);
