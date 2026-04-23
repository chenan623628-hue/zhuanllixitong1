"""
专利-标准比对系统 V1.0
M01 工程基线模块 - Worker 入口
"""
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def main():
    logger.info("Worker 服务启动中...")
    logger.info("专利-标准比对系统后台任务处理器")
    logger.info("Worker 服务已就绪，等待任务...")
    
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker 服务已停止")
