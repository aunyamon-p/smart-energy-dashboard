# Prompt สำหรับสั่ง AI พัฒนาต่อยอดเว็บไซต์

คุณคือ Senior Frontend Developer และ UI/UX Designer ช่วยพัฒนาเว็บไซต์ **Smart Energy Intelligence System** สำหรับติดตามการใช้พลังงานของอาคาร วิเคราะห์การใช้ไฟฟ้าที่ผิดปกติ และแสดงผลกระทบด้านพลังงานและค่าใช้จ่าย

## เป้าหมาย
สร้างเว็บ Dashboard ที่ดูเป็นผลิตภัณฑ์จริง ใช้งานง่าย อ่านข้อมูลได้ชัดเจน และเหมาะกับผู้ดูแลอาคารหรือผู้จัดการพลังงาน โดยเริ่มจาก Mock Data ก่อน ยังไม่ต้องเชื่อมต่อ AWS จนกว่าจะได้รับคำสั่ง

## Technology
- React + Vite + TypeScript
- React Router สำหรับ navigation
- Recharts สำหรับกราฟ
- Lucide React สำหรับ icons
- CSS หรือ Tailwind CSS โดยรักษา design system ให้สม่ำเสมอ
- เขียนโค้ดแยก Component และแยก data/service layer ให้พร้อมต่อ API ในอนาคต

## Scope: 3 Views, 2 Sidebar Menus
1. Overview
   - KPI: Total Energy Consumption (kWh), Estimated Electricity Cost (THB), Abnormal Spaces, Excess Energy (kWh)
   - กราฟ Actual Usage เทียบ Expected Usage ตามช่วงเวลา
   - กราฟเปรียบเทียบการใช้พลังงานตามอาคาร/ชั้น
   - Filters: Building, Floor, Date Range
   - Recent Anomalies แสดงสถานที่ วันเวลา Actual Usage, Excess Energy, Severity และ Status
2. Alerts
   - ตารางรายการความผิดปกติทั้งหมด
   - แสดง Alert ID, Building, Floor, Space, Date/Time, Actual Usage, Expected Usage, Excess Energy, Estimated Extra Cost, Severity และ Status
   - Search และ Filters ตาม Severity / Status
   - คลิกแถวเพื่อเปิดหน้า Alert Detail
3. Alert Detail
   - แสดงสถานที่และเวลาที่ตรวจพบ
   - Actual Usage เทียบ Expected Usage
   - Excess Energy และ Estimated Extra Cost
   - กราฟการใช้พลังงานช่วงที่ผิดปกติ
   - เหตุผลหรือกฎที่ทำให้ระบบแจ้งเตือน
   - เปลี่ยนสถานะ New / Acknowledged / Resolved ได้ใน prototype

Sidebar มีเพียง Overview และ Alerts เท่านั้น ไม่ต้องเพิ่มเมนู Analytics หรือ Cost Analysis แยก

## Visual Design
ใช้ Light Dashboard เท่านั้น:
- Main background: #F7F9FB
- Cards / Sidebar: #FFFFFF
- Primary Teal: #159A8A
- Soft Teal: #DDF3EE
- Heading: #1E293B
- Secondary text: #64748B
- Border: #E8EDF2
- Warning: #E5A63B
- Critical: #D9534F
- Normal/Resolved: muted green

แนวทาง:
- พื้นหลังสว่าง ไม่ใช้ dark theme หรือ dark sidebar
- Sidebar สีขาว
- Card สีขาว ขอบบาง เงานุ่ม มุมโค้งพอดี
- ใช้ whitespace ให้เพียงพอ
- กราฟอ่านง่าย ไม่ใช้สีมากเกินไป
- สีแดง/เหลืองสงวนไว้สำหรับระดับความผิดปกติ
- Typography อ่านง่ายและมีลำดับชัดเจน
- Responsive รองรับ desktop, tablet และ mobile
- หลีกเลี่ยงการตกแต่งมากเกินไป ให้ความสำคัญกับการอ่านข้อมูล

## Project Context
ระบบใช้ข้อมูลการใช้พลังงานย้อนหลังจาก dataset (เช่น CU-BEMS) เพื่อวิเคราะห์ความผิดปกติ ไม่ใช่การรับข้อมูล smart meter แบบ real-time ในเวอร์ชันนี้ควรใช้คำว่า historical data / batch analysis / simulated monitoring ให้ตรงกับข้อเท็จจริง

## Data & Integration
- เริ่มจาก Mock Data ที่มีหลายอาคาร หลายชั้น และหลายระดับความรุนแรง
- แสดงหน่วย kWh และ THB ชัดเจน
- แยกข้อมูลตัวอย่างออกจาก UI
- เตรียม API service layer สำหรับ:
  - GET /dashboard
  - GET /alerts
  - GET /alerts/:id
  - PATCH /alerts/:id (optional)
- ยังไม่ต้องสร้าง AWS resources หรือใส่ credentials
- ห้าม hardcode ตัวเลขตัวอย่างให้ดูเหมือนเป็นผลวิเคราะห์จริง
- ใส่หมายเหตุว่า Mock Data ใน prototype

## Code Quality & Deliverables
- เขียนโค้ดที่รันได้จริง ไม่มี placeholder ที่ทำให้หน้าเว็บพัง
- แยก components, pages, data และ services ให้เหมาะสม
- ตรวจสอบ TypeScript และ production build
- เพิ่ม README อธิบายการติดตั้งและรัน
- เมื่อทำเสร็จ ให้ส่งไฟล์ ZIP ของ source code ทั้งโปรเจกต์ โดยไม่รวม node_modules
- ระบุคำสั่งติดตั้งและรันอย่างชัดเจน
