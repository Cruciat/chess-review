import {
  LineChart,
  Line,
  YAxis,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis
} from 'recharts';

interface MoveData {
  ply: number;
  san: string;
  whiteWinPercent: number;
}

interface AdvantageChartProps {
  data: MoveData[];
  onMoveSelect: (ply: number) => void;
}

export default function AdvantageChart({ data, onMoveSelect }: AdvantageChartProps) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart 
        data={data} 
        onClick={(e) => {
          if (e?.activePayload) {
            onMoveSelect(e.activePayload[0].payload.ply);
          }
        }}
        margin={{ top: 10, right: 0, left: 0, bottom: 10 }}
      >
        <YAxis domain={[0, 100]} hide />
        <XAxis dataKey="ply" hide />
        <ReferenceLine y={50} stroke="#9ca3af" strokeDasharray="3 3" />
        
        <Tooltip
          formatter={(value: number) => [`${value}%`, 'Vittoria Bianco']}
          labelFormatter={(_, payloads) => {
            const move = payloads[0]?.payload;
            return move ? `${Math.ceil(move.ply / 2)}.${move.san}` : '';
          }}
          contentStyle={{ borderRadius: '0.5rem', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
        />
        
        <Line
          type="monotone"
          dataKey="whiteWinPercent"
          stroke="#1f2937"
          strokeWidth={3}
          dot={false}
          activeDot={{ r: 6, fill: '#3b82f6', strokeWidth: 0 }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
