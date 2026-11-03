export type AlertStatus = 'New' | 'Acknowledged' | 'Resolved'
export type Severity = 'High' | 'Medium' | 'Low'

export type EnergyAlert = {
  id: string
  building: string
  floor: string
  space: string
  date: string
  time: string
  actual: number
  expected: number
  excess: number
  cost: number
  severity: Severity
  status: AlertStatus
  reason: string
}

export const alerts: EnergyAlert[] = [
  { id: 'AL-2026-014', building: 'Engineering Building', floor: 'Floor 4', space: 'Computer Lab 401', date: '2026-11-03', time: '14:30', actual: 186, expected: 120, excess: 66, cost: 264, severity: 'High', status: 'New', reason: 'Energy consumption exceeded the expected baseline by 55%.' },
  { id: 'AL-2026-013', building: 'Engineering Building', floor: 'Floor 2', space: 'Meeting Room 205', date: '2026-11-03', time: '11:15', actual: 92, expected: 70, excess: 22, cost: 88, severity: 'Medium', status: 'Acknowledged', reason: 'Consumption remained above the normal range for multiple intervals.' },
  { id: 'AL-2026-012', building: 'Administration Building', floor: 'Floor 1', space: 'Office Area A', date: '2026-11-02', time: '16:45', actual: 145, expected: 110, excess: 35, cost: 140, severity: 'Medium', status: 'New', reason: 'A sustained increase was detected compared with the recent average.' },
  { id: 'AL-2026-011', building: 'Library Building', floor: 'Floor 3', space: 'Reading Zone', date: '2026-11-02', time: '09:00', actual: 78, expected: 72, excess: 6, cost: 24, severity: 'Low', status: 'Resolved', reason: 'A small deviation from the expected usage pattern was detected.' },
  { id: 'AL-2026-010', building: 'Library Building', floor: 'Floor 2', space: 'Study Room 2B', date: '2026-11-01', time: '19:20', actual: 130, expected: 85, excess: 45, cost: 180, severity: 'High', status: 'Acknowledged', reason: 'After-hours energy consumption was higher than expected.' },
  { id: 'AL-2026-009', building: 'Administration Building', floor: 'Floor 3', space: 'Server Room', date: '2026-10-31', time: '02:10', actual: 210, expected: 195, excess: 15, cost: 60, severity: 'Low', status: 'Resolved', reason: 'Overnight consumption was slightly above the normal baseline.' },
]

export const energyTrend = [
  { day: 'Oct 28', actual: 820, expected: 760 },
  { day: 'Oct 29', actual: 790, expected: 770 },
  { day: 'Oct 30', actual: 910, expected: 780 },
  { day: 'Oct 31', actual: 860, expected: 790 },
  { day: 'Nov 01', actual: 980, expected: 800 },
  { day: 'Nov 02', actual: 940, expected: 810 },
  { day: 'Nov 03', actual: 1080, expected: 820 },
]

export const buildingUsage = [
  { name: 'Engineering', usage: 3850 },
  { name: 'Administration', usage: 2920 },
  { name: 'Library', usage: 2480 },
  { name: 'Science', usage: 2160 },
]
