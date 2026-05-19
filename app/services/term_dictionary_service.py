"""
용어 자동 설명 시스템
주식 초보자를 위한 용어 설명 기능
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TermExplanation:
    """용어 설명 데이터 클래스"""
    term_name: str
    short_explanation: str
    detailed_explanation: str
    category: str
    example: Optional[str] = None


class TermDictionaryService:
    """주식 용어 설명 서비스"""
    
    # 용어 사전 데이터
    TERM_DICTIONARY: Dict[str, TermExplanation] = {
        "RSI": TermExplanation(
            term_name="RSI",
            short_explanation="최근 상승/하락 강도를 나타내는 지표입니다.",
            detailed_explanation="""
RSI(상대강도지수)는 최근 일정 기간(보통 14일) 동안 주가가 상승한 강도를 0~100으로 표현합니다.
- 70 이상: 단기 과열 가능성 (과도하게 오른 상태)
- 30 이하: 단기 과도 하락 가능성 (과도하게 내린 상태)
일반적으로 70 이상 구간에서는 급락 가능성, 30 이하 구간에서는 급등 가능성을 참고합니다.
이는 참고용 지표일 뿐 미래를 보장하지 않습니다.
            """,
            category="기술 지표",
            example="RSI 75: 단기 과열 가능성이 있음을 참고합니다."
        ),
        
        "MA5": TermExplanation(
            term_name="MA5",
            short_explanation="최근 5일 평균 가격입니다.",
            detailed_explanation="""
MA5(5일 이동평균)는 최근 5일 동안의 종가를 평균낸 가격입니다.
- 단기 추세를 매우 빠르게 반영합니다
- 변동성이 크므로 단기 매매자들이 많이 사용합니다
- 실시간으로 변하는 시장 심리를 반영합니다

현재 가격이 MA5보다 높으면 단기 상승, 낮으면 단기 하락 흐름입니다.
            """,
            category="이동평균선",
            example="현재 가격 > MA5: 단기 상승 흐름"
        ),
        
        "MA20": TermExplanation(
            term_name="MA20",
            short_explanation="최근 20일 평균 가격 흐름입니다.",
            detailed_explanation="""
MA20(20일 이동평균)은 최근 20일(약 1개월) 동안의 종가를 평균낸 가격입니다.
- 중기 추세를 표현합니다
- 단기 변동을 줄이고 추세를 명확하게 봅니다
- 기술적 분석에서 매우 중요한 지표입니다

MA5 > MA20 > MA60이면 강한 상승 추세, 반대면 하락 추세입니다.
            """,
            category="이동평균선",
            example="현재 가격 > MA20: 중기 상승 흐름"
        ),
        
        "MA60": TermExplanation(
            term_name="MA60",
            short_explanation="최근 60일 평균 가격입니다.",
            detailed_explanation="""
MA60(60일 이동평균)은 최근 60일(약 3개월) 동안의 종가를 평균낸 가격입니다.
- 장기 추세를 나타냅니다
- 장기 투자자들이 중요하게 보는 지표입니다
- 변동성이 작아 추세가 명확합니다

현재 가격이 MA60 위에 있으면 장기 상승 추세로 봅니다.
            """,
            category="이동평균선",
            example="현재 가격 > MA60: 장기 상승 추세"
        ),
        
        "거래량": TermExplanation(
            term_name="거래량",
            short_explanation="일정 기간 동안 거래된 주식의 수량입니다.",
            detailed_explanation="""
거래량은 하루 동안 실제로 거래(사고팔기)된 주식의 총 개수입니다.
- 거래량이 많으면 많은 투자자가 관심을 가진 상태입니다
- 거래량 증가는 추세 변화의 신호일 수 있습니다
- 가격 상승 시 거래량이 함께 증가하면 추세가 강한 것으로 봅니다

예: 평소 100만주 거래되는 종목이 500만주 거래되면 '거래량 급증'입니다.
            """,
            category="수급",
            example="거래량 5배 증가: 시장 관심도가 크게 높아진 상태"
        ),
        
        "거래대금": TermExplanation(
            term_name="거래대금",
            short_explanation="일정 기간 동안 거래된 금액의 총합입니다.",
            detailed_explanation="""
거래대금은 거래량에 가격을 곱한 금액입니다. (거래량 × 평균 가격 = 거래대금)
거래량과 함께 시장 관심도를 파악할 수 있습니다.
- 거래대금이 크면 많은 자금이 오고가는 상태입니다
- 소형주에서는 거래대금이 시가총액에 비해 커질 수 있습니다

예: 거래량 100만주 × 가격 50,000원 = 50억원의 거래대금
            """,
            category="수급",
            example="거래대금 1,000억원: 큰 규모의 자금이 움직이는 중"
        ),
        
        "외국인 순매수": TermExplanation(
            term_name="외국인 순매수",
            short_explanation="외국인 투자자가 더 많이 사간 현상입니다.",
            detailed_explanation="""
외국인 순매수는 외국인 투자자들의 순매수(매수량 - 매도량)를 의미합니다.
- 양수면 외국인이 더 많이 사고 있다는 뜻입니다
- 음수면 외국인이 더 많이 팔고 있다는 뜻입니다
- 외국인 자금 유입은 시장의 긍정적 신호로 보는 경향이 있습니다

예: 외국인 순매수 +10억원 = 외국인이 순(淨)으로 10억원 규모를 더 샀음
            """,
            category="수급",
            example="외국인 순매수 지속: 외국인 자금 유입이 계속되는 중"
        ),
        
        "기관 순매수": TermExplanation(
            term_name="기관 순매수",
            short_explanation="국내 기관투자자가 더 많이 사간 현상입니다.",
            detailed_explanation="""
기관 순매수는 국내 기관투자자(펀드, 보험사, 증권사 등)의 순매수를 의미합니다.
- 기관투자자는 장기 투자 관점에서 움직이는 경향이 있습니다
- 기관 순매수는 종목의 펀더멘탈이 좋다는 신호일 수 있습니다
- 개인투자자 반대 매매가 기관의 전략일 수도 있습니다

예: 기관 순매수 +5억원 = 기관이 순으로 5억원을 더 샀음
            """,
            category="수급",
            example="기관 순매수 연속 증가: 기관이 계속 매수하는 신호"
        ),
        
        "PER": TermExplanation(
            term_name="PER",
            short_explanation="현재 주가가 연간 순이익의 몇 배인지를 나타냅니다.",
            detailed_explanation="""
PER(주가수익비율) = 주가 ÷ 주당순이익
- PER가 낮으면 상대적으로 저평가되었다고 볼 수 있습니다
- PER가 높으면 상대적으로 고평가되었다고 볼 수 있습니다
- 업종별로 정상 PER이 다르므로 동업종 비교가 중요합니다

예: PER 10배 = 현재 이익 수준이 유지되면 10년 후 투자금 회수 개념
높은 PER은 시장이 미래 성장을 높게 평가하는 의미입니다.
            """,
            category="실적 지표",
            example="PER 25배: 동종업계 평균(20배)보다 높은 수준"
        ),
        
        "PBR": TermExplanation(
            term_name="PBR",
            short_explanation="현재 주가가 자산가치의 몇 배인지를 나타냅니다.",
            detailed_explanation="""
PBR(주가순자산비율) = 주가 ÷ 주당순자산
- PBR이 1.0 이하이면 자산가치보다 저렴한 가격입니다
- PBR이 높으면 시장이 높게 평가하는 것입니다
- 경기 안 좋을 때는 PBR이 낮은 종목이 주목받습니다

예: PBR 0.8 = 청산 가치보다 저렴한 가격
상대적으로 저평가된 종목 찾기에 자주 사용됩니다.
            """,
            category="실적 지표",
            example="PBR 0.7: 자산 가치보다 저렴하게 거래 중"
        ),
        
        "ROE": TermExplanation(
            term_name="ROE",
            short_explanation="회사가 주주 자본으로 얼마나 잘 수익을 내는지를 나타냅니다.",
            detailed_explanation="""
ROE(자기자본이익률) = 순이익 ÷ 자기자본
- ROE가 높으면 자본 효율성이 좋다는 뜻입니다
- 일반적으로 ROE 15% 이상이면 좋은 수준으로 봅니다
- 지속적으로 높은 ROE는 기업의 경쟁력을 나타냅니다

예: ROE 20% = 회사가 10년이면 자본의 2배를 번다는 의미
수익성이 좋은 회사를 찾는 중요한 지표입니다.
            """,
            category="실적 지표",
            example="ROE 25%: 업계 평균보다 높은 수익성"
        ),
        
        "변동성": TermExplanation(
            term_name="변동성",
            short_explanation="주가가 얼마나 크게 흔들리는지를 나타냅니다.",
            detailed_explanation="""
변동성은 일정 기간 동안 주가의 변동폭을 측정합니다.
- 변동성이 크면 급상승과 급락 가능성이 높습니다
- 변동성이 작으면 안정적이지만 기회도 적을 수 있습니다
- 단기 트레이더는 변동성이 큰 종목을 선호합니다

예: 변동성 30% = 연간 주가가 -30%~+30% 범위에서 움직일 가능성
높은 변동성 = 높은 위험성 + 높은 기회
            """,
            category="위험 지표",
            example="변동성 급증: 주가 등락이 커지고 있는 상태"
        ),
        
        "골든크로스": TermExplanation(
            term_name="골든크로스",
            short_explanation="단기 이동평균이 장기 이동평균을 위에서 아래로 뚫고 올라가는 현상입니다.",
            detailed_explanation="""
골든크로스는 기술적 분석에서 매우 주목받는 현상입니다.
- 예: MA5가 MA20을 뚫고 올라가면 '골든크로스'
- 보통 상승 신호로 해석됩니다
- 다만, 이후 과도하게 오를 수 있으므로 변동성이 증가할 수 있습니다

주의: 골든크로스가 모든 상승을 의미하지는 않으며, 참고용 신호일 뿐입니다.
반대로 데드크로스는 하강 신호로 봅니다.
            """,
            category="기술 신호",
            example="MA5 > MA20 > MA60 골든크로스 형성: 강한 상승 신호"
        ),
        
        "데드크로스": TermExplanation(
            term_name="데드크로스",
            short_explanation="단기 이동평균이 장기 이동평균을 위에서 아래로 뚫고 내려가는 현상입니다.",
            detailed_explanation="""
데드크로스는 골든크로스의 반대 현상입니다.
- 예: MA5가 MA20을 뚫고 내려가면 '데드크로스'
- 보통 하락 신호로 해석됩니다
- 이후 급락할 수 있으므로 주의가 필요합니다

주의: 데드크로스가 모든 하락을 의미하지는 않으며, 참고용 신호일 뿐입니다.
일시적인 조정일 수도 있으므로 다른 지표와 함께 봐야 합니다.
            """,
            category="기술 신호",
            example="MA5 < MA20 데드크로스 형성: 하락 신호 주의"
        ),
        
        "공매도": TermExplanation(
            term_name="공매도",
            short_explanation="먼저 빌려온 주식을 팔고, 나중에 사서 돌려주는 거래 방식입니다.",
            detailed_explanation="""
공매도는 '빈 팔기'라고도 불립니다.
1. 증권사로부터 주식을 빌립니다
2. 빌려온 주식을 현재 가격에 팝니다 (공매도)
3. 나중에 주가가 떨어졌을 때 사서 원금을 돌려줍니다
4. 차익을 취합니다

- 공매도가 증가하면 약세 신호로 봅니다
- 다만, 대규모 공매도는 과도한 하락에 대한 '공급' 역할을 합니다
- 일부는 헤징 목적의 정상적인 거래입니다

주의: 공매도 비율이 높다고 항상 부정적이지 않으며, 시장 기제의 일부입니다.
            """,
            category="수급",
            example="공매도 급증: 공매도자들이 주가 하락을 예상하는 상태"
        ),
        
        "상대강도": TermExplanation(
            term_name="상대강도",
            short_explanation="특정 종목의 주가 움직임을 시장 평균과 비교합니다.",
            detailed_explanation="""
상대강도(상대강도지수)는 종목의 강세/약세를 시장 대비로 봅니다.
- 상대강도 > 1.0: 시장 평균보다 강한 성과
- 상대강도 < 1.0: 시장 평균보다 약한 성과
- 강한 상대강도의 종목이 강세장에서 선호됩니다

예: 코스피 +1%일 때 A종목 +3% = 강한 상대강도
특정 테마가 부각될 때 해당 종목이 강한 상대강도를 보입니다.
            """,
            category="기술 지표",
            example="상대강도 강화: 시장보다 빠르게 상승 중"
        ),
        
        "테마": TermExplanation(
            term_name="테마",
            short_explanation="주가를 움직이는 핵심 이야기(story)입니다.",
            detailed_explanation="""
테마는 '시장이 주목하는 공통의 이야기'를 의미합니다.
- AI 테마: AI 관련 기업들이 함께 주목받는 현상
- 2차전지 테마: 전기차 시장 성장으로 배터리 기업들 주목
- 반도체 테마: 반도체 수급 개선으로 관련주 강세

테마는:
- 시간이 지나면서 변합니다 (순환성)
- 강한 테마는 개별 실적보다 우선할 수 있습니다
- 테마 쇠퇴 시 가격도 함께 하락할 수 있습니다

시장에서 '핫'한 것이 곧 좋은 투자는 아닙니다.
            """,
            category="시장 현상",
            example="AI 테마 강세: AI 관련 종목들이 함께 상승 중"
        ),
        
        "거래량 증가율": TermExplanation(
            term_name="거래량 증가율",
            short_explanation="거래량이 평소 대비 얼마나 증가했는지를 비율로 나타냅니다.",
            detailed_explanation="""
거래량 증가율 = (현재 거래량 - 평균 거래량) / 평균 거래량 × 100%

예시:
- 평균 거래량: 100만주
- 현재 거래량: 250만주
- 거래량 증가율: 150% (2.5배)

거래량 급증은:
- 시장 관심도 증가의 신호
- 큰 기관이나 외국인의 매매 신호일 수 있음
- 가격 변동의 신뢰성을 높입니다

주의: 거래량 증가만으로는 상승을 보장하지 않습니다.
            """,
            category="수급",
            example="거래량 증가율 300%: 평소의 4배 수준으로 거래 중"
        ),
    }
    
    @classmethod
    def get_all_terms(cls) -> List[str]:
        """모든 용어 목록 반환"""
        return list(cls.TERM_DICTIONARY.keys())
    
    @classmethod
    def get_term_explanation(cls, term_name: str) -> Optional[TermExplanation]:
        """
        특정 용어의 설명 조회
        
        Args:
            term_name: 용어명
            
        Returns:
            TermExplanation 객체 또는 None
        """
        # 대소문자 무시하고 검색
        for key, value in cls.TERM_DICTIONARY.items():
            if key.lower() == term_name.lower():
                return value
        return None
    
    @classmethod
    def get_short_explanation(cls, term_name: str) -> Optional[str]:
        """용어의 짧은 설명만 조회"""
        explanation = cls.get_term_explanation(term_name)
        return explanation.short_explanation if explanation else None
    
    @classmethod
    def get_detailed_explanation(cls, term_name: str) -> Optional[str]:
        """용어의 상세 설명만 조회"""
        explanation = cls.get_term_explanation(term_name)
        return explanation.detailed_explanation if explanation else None
    
    @classmethod
    def search_terms_by_category(cls, category: str) -> List[TermExplanation]:
        """카테고리별 용어 검색"""
        return [
            term for term in cls.TERM_DICTIONARY.values()
            if term.category.lower() == category.lower()
        ]
    
    @classmethod
    def get_related_terms(cls, term_name: str, limit: int = 5) -> List[str]:
        """
        관련 용어 추천
        같은 카테고리의 다른 용어 반환
        """
        explanation = cls.get_term_explanation(term_name)
        if not explanation:
            return []
        
        related = [
            term.term_name for term in cls.TERM_DICTIONARY.values()
            if term.category == explanation.category and term.term_name != term_name
        ]
        return related[:limit]


# 싱글톤 인스턴스
term_dictionary = TermDictionaryService()
