"""
FundPilot-AI SMTP 邮件发送模块
支持 SSL/TLS 和多张内嵌图片
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from typing import Optional

from core.config import get_config
from core.logger import get_logger

logger = get_logger("email_sender")


class EmailSender:
    """邮件发送器"""
    
    def __init__(self):
        config = get_config()
        self.smtp_server = config.email.smtp_server
        self.smtp_port = config.email.smtp_port
        self.sender = config.email.sender
        self.password = config.email.password
        self.receivers = config.email.receivers
    
    def send(
        self,
        subject: str,
        html_content: str,
        chart_image: Optional[bytes] = None,
        receivers: Optional[list[str]] = None
    ) -> bool:
        """
        发送邮件（单图版，兼容旧接口）
        
        Args:
            subject: 邮件标题
            html_content: HTML 内容
            chart_image: 图表图片（PNG 字节流）
            receivers: 收件人列表（不指定则使用配置）
        
        Returns:
            是否发送成功
        """
        images = {"trend_chart": chart_image} if chart_image else None
        return self.send_with_images(subject, html_content, images, receivers)
    
    def send_with_images(
        self,
        subject: str,
        html_content: str,
        images: Optional[dict[str, bytes]] = None,
        receivers: Optional[list[str]] = None
    ) -> bool:
        """
        发送带多张图片的邮件
        
        Args:
            subject: 邮件标题
            html_content: HTML 内容
            images: 图片字典 {cid: bytes}，HTML 中用 cid:xxx 引用
            receivers: 收件人列表
        
        Returns:
            是否发送成功
        """
        receivers = receivers or self.receivers
        
        if not receivers:
            logger.warning("没有配置收件人，跳过发送")
            return False
        
        try:
            # 创建邮件
            msg = MIMEMultipart('related')
            msg['Subject'] = subject
            msg['From'] = self.sender
            msg['To'] = ', '.join(receivers)
            
            # HTML 内容
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 内嵌多张图片
            if images:
                for cid, image_bytes in images.items():
                    if image_bytes:
                        img = MIMEImage(image_bytes)
                        img.add_header('Content-ID', f'<{cid}>')
                        img.add_header('Content-Disposition', 'inline', filename=f'{cid}.png')
                        msg.attach(img)
            
            # 发送
            logger.info(f"连接 SMTP 服务器: {self.smtp_server}:{self.smtp_port}")
            
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.sender, self.password)
                server.sendmail(self.sender, receivers, msg.as_string())
            
            logger.info(f"邮件发送成功: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
    
    def send_simple(self, subject: str, content: str) -> bool:
        """
        发送简单文本邮件
        
        Args:
            subject: 标题
            content: 文本内容
        
        Returns:
            是否成功
        """
        if not self.receivers:
            logger.warning("没有配置收件人，跳过发送")
            return False
        
        try:
            msg = MIMEText(content, 'plain', 'utf-8')
            msg['Subject'] = subject
            msg['From'] = self.sender
            msg['To'] = ', '.join(self.receivers)
            
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.sender, self.password)
                server.sendmail(self.sender, self.receivers, msg.as_string())
            
            logger.info(f"简单邮件发送成功: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"简单邮件发送失败: {e}")
            return False


# 全局发送器实例
_sender: Optional[EmailSender] = None


def get_email_sender() -> EmailSender:
    """获取邮件发送器单例"""
    global _sender
    if _sender is None:
        _sender = EmailSender()
    return _sender


def send_decision_email(
    subject: str,
    html_content: str,
    chart_image: Optional[bytes] = None
) -> bool:
    """
    发送决策邮件（便捷函数，单图版）
    """
    sender = get_email_sender()
    return sender.send(subject, html_content, chart_image)


def send_combined_report(
    subject: str,
    html_content: str,
    charts: dict[str, bytes]
) -> bool:
    """
    发送合并决策报告（多图版）
    
    Args:
        subject: 邮件标题
        html_content: HTML 内容
        charts: 图表字典 {cid: bytes}
    
    Returns:
        是否成功
    """
    sender = get_email_sender()
    return sender.send_with_images(subject, html_content, charts)


def send_error_notification(error_message: str) -> bool:
    """
    发送错误通知
    """
    sender = get_email_sender()
    return sender.send_simple(
        "【FundPilot】系统异常通知",
        f"FundPilot-AI 运行出现异常：\n\n{error_message}\n\n请检查系统日志。"
    )
