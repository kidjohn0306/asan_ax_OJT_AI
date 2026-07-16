import { useMatch, useNavigate } from 'react-router-dom'

export default function ExamManagementPage({ renderManagement }) {
  const detailMatch = useMatch('/admin/exams/:examId')
  const navigate = useNavigate()
  const selectedExamId = detailMatch?.params.examId || null

  function selectExam(examId) {
    navigate(examId ? `/admin/exams/${encodeURIComponent(examId)}` : '/admin/exams')
  }

  return renderManagement({ selectedExamId, onSelectExam:selectExam })
}
