import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  useTheme,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  TrendingFlat,
} from '@mui/icons-material';

interface MetricCardProps {
  title: string;
  value: React.ReactNode;
  icon: React.ReactNode;
  color: 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success';
  trend?: 'up' | 'down' | 'stable';
  subtitle?: string;
  onClick?: () => void;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  icon,
  color,
  trend,
  subtitle,
  onClick,
}) => {
  const theme = useTheme();

  const getTrendIcon = () => {
    if (!trend) return null;

    const iconProps = {
      fontSize: 'small' as const,
      sx: { ml: 1 },
    };

    switch (trend) {
      case 'up':
        return <TrendingUp {...iconProps} color="success" />;
      case 'down':
        return <TrendingDown {...iconProps} color="error" />;
      case 'stable':
        return <TrendingFlat {...iconProps} color="action" />;
      default:
        return null;
    }
  };

  const getTrendColor = () => {
    if (!trend) return 'default';
    
    switch (trend) {
      case 'up':
        return theme.palette.success.main;
      case 'down':
        return theme.palette.error.main;
      case 'stable':
        return theme.palette.grey[500];
      default:
        return theme.palette.grey[500];
    }
  };

  return (
    <Card
      sx={{
        height: '100%',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.3s ease',
        '&:hover': onClick
          ? {
              transform: 'translateY(-4px)',
              boxShadow: 4,
            }
          : {},
      }}
      onClick={onClick}
    >
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="start">
          <Box flex={1}>
            <Typography
              color="textSecondary"
              gutterBottom
              variant="body2"
              sx={{ fontWeight: 500 }}
            >
              {title}
            </Typography>
            <Box display="flex" alignItems="center">
              <Typography
                variant="h4"
                component="div"
                sx={{ fontWeight: 700 }}
              >
                {value}
              </Typography>
              {getTrendIcon()}
            </Box>
            {subtitle && (
              <Typography
                variant="caption"
                color="textSecondary"
                sx={{ mt: 1, display: 'block' }}
              >
                {subtitle}
              </Typography>
            )}
          </Box>
          <Box
            sx={{
              backgroundColor: theme.palette[color].light,
              borderRadius: '50%',
              p: 1.5,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Box
              sx={{
                color: theme.palette[color].main,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {icon}
            </Box>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default MetricCard;