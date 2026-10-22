"""AI Agent Service — Cố vấn Thể dục & Dinh dưỡng Cá nhân hóa (FitAI Advisor)."""
import asyncio
import logging
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage

from core.config import settings

logger = logging.getLogger(__name__)


class ChatAgentException(Exception):
    """Ngoại lệ khi gọi mô hình AI hoặc khi phản hồi không hợp lệ."""

    def __init__(self, message: str, status_code: int = 503) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def build_system_prompt(profile_data: Optional[dict] = None) -> str:
    """Xây dựng system prompt cá nhân hóa cho FitAI Advisor từ hồ sơ và chỉ số tính toán."""
    if not profile_data:
        profile_section = "Người dùng chưa cung cấp thông tin hồ sơ sức khỏe."
    else:
        age = profile_data.get("age") or "chưa có thông tin"
        gender_raw = profile_data.get("gender")
        gender_map = {"male": "Nam", "female": "Nữ", "other": "Khác"}
        gender = gender_map.get(gender_raw, gender_raw or "chưa có thông tin")
        height = (
            f"{profile_data.get('height_cm')} cm"
            if profile_data.get("height_cm") is not None
            else "chưa có thông tin"
        )
        weight = (
            f"{profile_data.get('weight_kg')} kg"
            if profile_data.get("weight_kg") is not None
            else "chưa có thông tin"
        )

        act_raw = profile_data.get("activity_level")
        act_map = {
            "sedentary": "Ít vận động (làm việc văn phòng, ít đi lại)",
            "light": "Vận động nhẹ (tập 1–3 ngày/tuần)",
            "moderate": "Vận động vừa (tập 3–5 ngày/tuần)",
            "active": "Năng động (tập thể thao 6–7 ngày/tuần)",
            "very_active": "Rất năng động (vận động viên, lao động nặng)",
        }
        activity = act_map.get(act_raw, act_raw or "chưa có thông tin")

        goal_raw = profile_data.get("fitness_goal")
        goal_map = {
            "weight_loss": "Giảm cân / giảm mỡ thừa",
            "muscle_gain": "Tăng cơ bắp, cải thiện vóc dáng",
            "maintenance": "Duy trì cân nặng & sức khỏe tốt",
            "endurance": "Tăng cường sức bền thể lực",
        }
        goal = goal_map.get(goal_raw, goal_raw or "chưa có thông tin")
        dietary = profile_data.get("dietary_restrictions") or "Không có dị ứng hay kiêng cữ đặc biệt"

        metrics = profile_data.get("metrics")
        if metrics and metrics.get("is_complete"):
            floor_note = " (đã áp dụng mức sàn an toàn tối thiểu)" if metrics.get("calorie_floor_applied") else ""
            metrics_info = (
                f"- Chỉ số BMI: {metrics.get('bmi')} ({metrics.get('bmi_category')})\n"
                f"- Chỉ số BMR: {metrics.get('bmr')} kcal/ngày\n"
                f"- Chỉ số TDEE: {metrics.get('tdee')} kcal/ngày\n"
                f"- Calo mục tiêu: {metrics.get('target_calories')} kcal/ngày{floor_note}\n"
                f"- Nhu cầu dinh dưỡng hàng ngày (Macro): "
                f"Protein {metrics.get('protein_g')}g, Chất béo {metrics.get('fat_g')}g, Tinh bột {metrics.get('carb_g')}g."
            )
        else:
            metrics_info = "- Các chỉ số cơ thể (BMI, BMR, TDEE, Calo mục tiêu, Macro): chưa có thông tin (hồ sơ chưa điền đầy đủ)."

        profile_section = f"""Thông tin hồ sơ sức khỏe của người dùng hiện tại:
- Tuổi: {age}
- Giới tính: {gender}
- Chiều cao: {height}
- Cân nặng: {weight}
- Mức độ vận động: {activity}
- Mục tiêu thể hình: {goal}
- Dị ứng / Thực phẩm kiêng: {dietary}
{metrics_info}"""

    return f"""Bạn là FitAI — Chuyên gia cố vấn thông minh về thể dục, thể hình và dinh dưỡng cá nhân hóa.

{profile_section}

QUY TẮC BẮT BUỘC KHI TƯ VẤN:
1. Luôn trả lời bằng TIẾNG VIỆT tự nhiên, thân thiện, rõ ràng, mang tính động viên và có căn cứ khoa học thể thao/dinh dưỡng.
2. DỰA TRÊN HỒ SƠ ĐÃ CUNG CẤP: Hãy sử dụng các chỉ số calo mục tiêu, phân bổ macro và mục tiêu của người dùng ở trên để đưa ra tư vấn thiết thực. Với các mục ghi "chưa có thông tin", chỉ dùng những gì đã có và nhẹ nhàng gợi ý người dùng cập nhật hồ sơ để nhận tư vấn chính xác nhất.
3. TUYỆT ĐỐI KHÔNG TỰ TÍNH LẠI CHỈ SỐ: Không tự tính hay bịa đặt lại chỉ số BMR/TDEE/Calo khác với số liệu do hệ thống đã tính ở trên.
4. NGUYÊN TẮC AN TOÀN Y TẾ:
   - Bạn KHÔNG PHẢI là bác sĩ y khoa và KHÔNG ĐƯỢC chẩn đoán bệnh tật, không kê đơn thuốc.
   - Đối với các câu hỏi về bệnh lý nguy hiểm, triệu chứng đau đớn, chấn thương thực thể, bạn PHẢI khuyên người dùng đến gặp bác sĩ hoặc cơ sở y tế chuyên khoa để được thăm khám.
"""


class FitnessAdvisorAgent:
    """Agent sử dụng mô hình Google Gemini để tư vấn thể dục và dinh dưỡng."""

    def __init__(self) -> None:
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.7,
            convert_system_message_to_human=True,
        )

    async def chat(
        self,
        history: list[dict],
        user_message: str,
        profile_data: Optional[dict] = None,
    ) -> str:
        """Gửi tin nhắn kèm lịch sử và ngữ cảnh hồ sơ cá nhân hóa đến AI Agent.

        Args:
            history: Danh sách 10 tin nhắn gần nhất TRƯỚC tin hiện tại
                     [{"role": "user"|"assistant", "content": "..."}]
            user_message: Tin nhắn mới nhất của người dùng.
            profile_data: Dữ liệu hồ sơ và các chỉ số tính toán.

        Returns:
            Nội dung câu trả lời của AI.
        """
        system_prompt = build_system_prompt(profile_data)
        messages = [SystemMessage(content=system_prompt)]

        for msg in history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        # Tin nhắn hiện tại được thêm riêng vào cuối danh sách ngữ cảnh
        messages.append(HumanMessage(content=user_message))

        try:
            response = await asyncio.wait_for(
                self.llm.ainvoke(messages),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.error("FitnessAdvisorAgent timeout sau 30s")
            raise ChatAgentException(
                "Hệ thống AI phản hồi quá thời gian quy định (timeout 30s). Vui lòng thử lại sau.",
                status_code=504,
            )
        except Exception as e:
            # Tuyệt đối không log nội dung tin nhắn, API key hay thông tin hồ sơ
            logger.error("FitnessAdvisorAgent error: %s", type(e).__name__)
            raise ChatAgentException(
                "Dịch vụ AI tạm thời không khả dụng hoặc bị gián đoạn kết nối. Vui lòng thử lại sau.",
                status_code=503,
            )

        reply_content = getattr(response, "content", None)
        if not reply_content or not str(reply_content).strip():
            logger.warning("FitnessAdvisorAgent returned empty or safety-blocked content")
            raise ChatAgentException(
                "Phản hồi từ AI bị rỗng hoặc bị chặn bởi bộ lọc an toàn. Vui lòng thử lại câu hỏi khác.",
                status_code=502,
            )

        return str(reply_content).strip()


# Singleton agent instance
fitness_agent = FitnessAdvisorAgent()
