export const mockStats = {
  active_requests: 4,
  donors_notified: 11,
  confirmed_today: 2,
  avg_match_time: "2.4h",
};

export const mockRequests = [
  {
    id: "req-001",
    urgency: "urgent",
    status: "pending",
    predicted_date: "2025-06-12",
    patient: { name: "Aarav Sharma",  blood_type: "B+",  city: "Delhi" },
  },
  {
    id: "req-002",
    urgency: "normal",
    status: "matched",
    predicted_date: "2025-06-17",
    patient: { name: "Priya Nair",    blood_type: "O+",  city: "Mumbai" },
  },
  {
    id: "req-003",
    urgency: "planned",
    status: "fulfilled",
    predicted_date: "2025-06-24",
    patient: { name: "Ravi Kumar",    blood_type: "A+",  city: "Bengaluru" },
  },
  {
    id: "req-004",
    urgency: "urgent",
    status: "pending",
    predicted_date: "2025-06-11",
    patient: { name: "Meena Iyer",    blood_type: "AB+", city: "Chennai" },
  },
  {
    id: "req-005",
    urgency: "normal",
    status: "matched",
    predicted_date: "2025-06-19",
    patient: { name: "Arjun Patel",   blood_type: "B-",  city: "Mumbai" },
  },
];

export const mockDonors = [
  { id: "d-01", name: "Suresh Reddy",    blood_type: "B+",  city: "Delhi",     match_score: 92, last_donation: "2025-01-10", confirmed: false },
  { id: "d-02", name: "Kavitha Rao",     blood_type: "O+",  city: "Delhi",     match_score: 87, last_donation: "2025-02-22", confirmed: false },
  { id: "d-03", name: "Vikram Singh",    blood_type: "B+",  city: "Delhi",     match_score: 83, last_donation: "2024-12-05", confirmed: true  },
  { id: "d-04", name: "Neha Gupta",      blood_type: "A+",  city: "Delhi",     match_score: 76, last_donation: "2025-03-14", confirmed: false },
  { id: "d-05", name: "Rohit Desai",     blood_type: "O+",  city: "Mumbai",    match_score: 95, last_donation: "2025-01-30", confirmed: false },
  { id: "d-06", name: "Pooja Mehta",     blood_type: "O-",  city: "Mumbai",    match_score: 90, last_donation: "2024-11-18", confirmed: true  },
  { id: "d-07", name: "Deepak Kulkarni", blood_type: "B+",  city: "Mumbai",    match_score: 81, last_donation: "2025-02-08", confirmed: false },
  { id: "d-08", name: "Divya Menon",     blood_type: "O-",  city: "Bengaluru", match_score: 98, last_donation: "2024-12-18", confirmed: false },
  { id: "d-09", name: "Manjunath S",     blood_type: "A+",  city: "Bengaluru", match_score: 79, last_donation: "2025-03-05", confirmed: false },
  { id: "d-10", name: "Anita Chauhan",   blood_type: "B-",  city: "Delhi",     match_score: 88, last_donation: "2025-04-08", confirmed: true  },
];
