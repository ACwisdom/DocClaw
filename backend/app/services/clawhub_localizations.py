"""ClawHub 技能广场展示文案（中文）。"""

from __future__ import annotations

from dataclasses import dataclass

from .clawhub_client import ParsedClawHubSkill


@dataclass(frozen=True)
class SkillZhCopy:
    name: str
    description: str
    scenarios: str
    highlights: str = "来自 ClawHub 开放技能注册表"


CLAWHUB_ZH: dict[str, SkillZhCopy] = {
    "medical-qa": SkillZhCopy(
        name="医疗健康问答",
        description="帮助用户理解症状含义、解读检查报告、了解用药常识，并提供何时就医的专业建议。",
        scenarios="健康症状咨询、检查报告解读、药品说明、就医时机建议",
        highlights="温暖共情的患者向问答，强调安全边界与及时就医引导",
    ),
    "medical-document-processor": SkillZhCopy(
        name="医疗文档处理器",
        description="处理医疗文书：病历摘要、报告分析、医学文献整理，适用于医生与医疗专业人员。",
        scenarios="病历摘要、医疗报告分析、出院小结、门诊记录整理",
        highlights="支持多种临床文档格式的结构化提取与摘要",
    ),
    "medical-research-toolkit": SkillZhCopy(
        name="医学研究工具包",
        description="统一查询 14+ 生物医学数据库，支持药物重定位、靶点发现、临床试验与文献检索（ChEMBL、PubMed、ClinicalTrials.gov 等）。",
        scenarios="疾病靶点研究、上市/在研药物检索、临床证据检索、化合物活性分析",
        highlights="通过统一 MCP 端点访问多库，适合科研与循证检索",
    ),
    "clinical-doc-assistant": SkillZhCopy(
        name="临床文档助手",
        description="协助临床人员起草与结构化病历文档，包括 SOAP 记录、转诊信、事前授权、出院小结与照护计划；可对接 FHIR 电子病历或基于手工录入生成草稿。",
        scenarios="SOAP 病历、转诊信、事前授权、出院小结、照护计划撰写",
        highlights="仅辅助文档撰写，不替代临床诊断与处方决策",
    ),
    "clinical-data-extractor": SkillZhCopy(
        name="临床数据提取器",
        description="从网页或 PDF 中提取结构化临床试验数据，包括药名、厂商、适应症、分期及关键试验信息。",
        scenarios="临床试验资料整理、文献与注册库页面解析",
        highlights="自动从 URL/PDF 抽取试验核心字段",
    ),
    "ecg-ai-diagnosis": SkillZhCopy(
        name="心电图 AI 分析",
        description="通过心之语 API 分析心电图信号，支持单导联与 12 导联，根据输入自动选择分析接口。",
        scenarios="胸闷心悸初筛、心电图异常线索提炼、心电随访对比",
        highlights="对接专业心电 AI 服务，适合门诊快速初筛",
    ),
    "pubmed-literature-search": SkillZhCopy(
        name="PubMed 临床医学文献检索",
        description="面向临床医学的 PubMed 文献检索与分析，支持按 JCR 分区、影响因子等条件筛选与综合排序。",
        scenarios="医学文献检索、临床研究综述、特定疾病治疗方案证据查找",
        highlights="支持影响因子筛选与多维度文献排序",
    ),
    "pubmed-search-skill": SkillZhCopy(
        name="PubMed 文献搜索",
        description="基于 AI 的 PubMed 生物医学文献搜索与分析工具。",
        scenarios="快速检索生物医学论文、循证参考、课题背景调研",
        highlights="自然语言检索 PubMed 文献并生成要点摘要",
    ),
    "virtual-patient-roleplay": SkillZhCopy(
        name="虚拟患者角色扮演",
        description="模拟标准化患者接诊场景，用于 OSCE 式病史采集、医患沟通与临床思维训练。",
        scenarios="医学生/住院医师问诊训练、沟通技巧演练、OSCE 备考",
        highlights="可配置病例与患者人设，支持反复练习",
    ),
    "patient-consent-simplifier": SkillZhCopy(
        name="知情同意书通俗化",
        description="将知情同意等医疗法律文档改写为患者易懂表述，同时兼顾 FDA 21 CFR 50 等合规要求。",
        scenarios="术前/用药/检查知情同意说明、患者宣教材料撰写",
        highlights="在可读性与法规合规之间取得平衡",
    ),
    "clinical-trial": SkillZhCopy(
        name="临床试验检索",
        description="检索类似 ClinicalTrials.gov 的临床试验数据库，查询适应症、分期、入组状态与试验设计等信息。",
        scenarios="患者转诊前查试验、科研选题、在研疗法调研",
        highlights="聚合临床试验注册信息，支持自然语言查询",
    ),
}


def localize_clawhub_skill(parsed: ParsedClawHubSkill) -> ParsedClawHubSkill:
    copy = CLAWHUB_ZH.get(parsed.slug)
    if not copy:
        return parsed
    return ParsedClawHubSkill(
        slug=parsed.slug,
        name=copy.name,
        description=copy.description,
        system_prompt=parsed.system_prompt,
        version=parsed.version,
        author=parsed.author,
        publisher=parsed.publisher,
        install_count=parsed.install_count,
        rating=parsed.rating,
        tags=parsed.tags,
        updated_at=parsed.updated_at,
        category=parsed.category,
        scenarios=copy.scenarios,
        compatibility=parsed.compatibility,
        highlights=copy.highlights,
    )


def apply_localizations_to_db(db) -> int:
    from ..models import StoreSkill

    updated = 0
    for row in db.query(StoreSkill).filter(StoreSkill.clawhub_slug.isnot(None)).all():
        copy = CLAWHUB_ZH.get(row.clawhub_slug or "")
        if not copy:
            continue
        row.name = copy.name
        row.description = copy.description
        row.scenarios = copy.scenarios
        row.highlights = copy.highlights
        updated += 1
    if updated:
        db.commit()
    return updated
